#!/usr/bin/env python3
"""Bounded Responses proxy for a separately isolated, opt-in CI worker.

The API key must live only in this process/container. This proxy is not a
multi-tenant service or a substitute for OS/container isolation.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

MAX_REQUEST_BYTES = 2_000_000
MAX_RESPONSE_BYTES = 20_000_000
UPSTREAM_HOST = "api.openai.com"


class GatewayServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        address: tuple[str, int],
        *,
        api_key: str,
        model: str,
        max_requests: int,
        max_duration_seconds: int,
    ) -> None:
        if not api_key or not model or max_requests <= 0 or max_duration_seconds <= 0:
            raise ValueError("gateway requires a key, model and positive limits")
        super().__init__(address, GatewayHandler)
        self.api_key = api_key
        self.model = model
        self.max_requests = max_requests
        self.deadline = time.monotonic() + max_duration_seconds
        self.request_count = 0
        self.counter_lock = threading.Lock()
        self.slots = threading.BoundedSemaphore(2)

    def reserve(self) -> bool:
        with self.counter_lock:
            if time.monotonic() >= self.deadline or self.request_count >= self.max_requests:
                return False
            self.request_count += 1
            return True


class GatewayHandler(BaseHTTPRequestHandler):
    server: GatewayServer
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:
        # Do not log request bodies, headers, upstream responses or credentials.
        return None

    def _error(self, status: int, message: str) -> None:
        body = json.dumps({"error": message}).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/healthz":
            body = b'{"status":"ready"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        else:
            self._error(404, "not found")

    def do_POST(self) -> None:
        if self.path != "/v1/responses":
            self._error(404, "not found")
            return
        length = self.headers.get("Content-Length", "")
        if not length.isdecimal() or not 0 < int(length) <= MAX_REQUEST_BYTES:
            self._error(413, "invalid request size")
            return
        if self.headers.get("Content-Type", "").split(";", 1)[0] != "application/json":
            self._error(415, "JSON request required")
            return
        body = self.rfile.read(int(length))
        try:
            request = json.loads(body)
        except (ValueError, UnicodeDecodeError):
            self._error(400, "invalid JSON")
            return
        if not isinstance(request, dict) or request.get("model") != self.server.model:
            self._error(403, "model not allowed")
            return
        if not self.server.slots.acquire(blocking=False):
            self._error(429, "gateway busy")
            return
        try:
            if not self.server.reserve():
                self._error(429, "gateway limit reached")
                return
            self._forward(body)
        finally:
            self.server.slots.release()

    def _forward(self, body: bytes) -> None:
        connection = http.client.HTTPSConnection(UPSTREAM_HOST, timeout=180)
        headers = {
            "Authorization": "Bearer " + self.server.api_key,
            "Content-Type": "application/json",
            "Accept": "text/event-stream, application/json",
        }
        try:
            connection.request("POST", "/v1/responses", body=body, headers=headers)
            response = connection.getresponse()
        except (OSError, http.client.HTTPException):
            connection.close()
            self._error(502, "upstream unavailable")
            return
        try:
            self.send_response(response.status)
            self.send_header("Content-Type", response.getheader("Content-Type", "application/json"))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            total = 0
            while chunk := response.read1(8192):
                total += len(chunk)
                if total > MAX_RESPONSE_BYTES:
                    self.close_connection = True
                    return
                self.wfile.write(f"{len(chunk):x}\r\n".encode() + chunk + b"\r\n")
                self.wfile.flush()  # SSE must not wait for the full response.
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()
        except (OSError, http.client.HTTPException):
            self.close_connection = True
        finally:
            connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--model", required=True)
    parser.add_argument("--max-requests", type=int, default=120)
    parser.add_argument("--max-duration-seconds", type=int, default=1800)
    args = parser.parse_args()
    key = os.environ.get("OPENAI_API_KEY", "")
    server = GatewayServer(
        ("127.0.0.1", args.port),
        api_key=key,
        model=args.model,
        max_requests=args.max_requests,
        max_duration_seconds=args.max_duration_seconds,
    )
    print("Responses gateway ready", flush=True)
    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
