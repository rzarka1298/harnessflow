"""The key-bearing gateway forwards only bounded, fixed-model Responses calls."""

from __future__ import annotations

import http.client
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from typing import ClassVar
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "ci_model_gateway", Path(__file__).parents[1] / "ci-model-gateway.py"
)
assert SPEC and SPEC.loader
gateway = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gateway)


class StubResponse:
    status = 200

    def __init__(self) -> None:
        self.chunks = [b"data: first\n\n", b"data: second\n\n"]

    def getheader(self, name: str, default: str = "") -> str:
        return "text/event-stream" if name == "Content-Type" else default

    def read1(self, size: int) -> bytes:
        return self.chunks.pop(0) if self.chunks else b""


class StubUpstream:
    observed: ClassVar[list[tuple[str, str, bytes, dict[str, str]]]] = []

    def __init__(self, host: str, timeout: int) -> None:
        assert host == "api.openai.com"
        assert timeout == 180

    def request(self, method: str, path: str, body: bytes, headers: dict[str, str]) -> None:
        self.observed.append((method, path, body, headers))

    def getresponse(self) -> StubResponse:
        return StubResponse()

    def close(self) -> None:
        pass


class GatewayTests(unittest.TestCase):
    def setUp(self) -> None:
        StubUpstream.observed = []
        self.server = gateway.GatewayServer(
            ("127.0.0.1", 0),
            api_key="upstream-secret",
            model="test-model",
            max_requests=1,
            max_duration_seconds=60,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, method: str, path: str, body: bytes = b"") -> tuple[int, bytes]:
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        try:
            connection.request(
                method,
                path,
                body=body,
                headers={"Content-Type": "application/json", "Authorization": "Bearer attacker"},
            )
            response = connection.getresponse()
            return response.status, response.read()
        finally:
            connection.close()

    def test_forwards_sse_with_only_server_credential(self) -> None:
        with patch.object(gateway.http.client, "HTTPSConnection", StubUpstream):
            status, body = self.request("POST", "/v1/responses", b'{"model":"test-model"}')
        self.assertEqual(status, 200)
        self.assertEqual(body, b"data: first\n\ndata: second\n\n")
        self.assertEqual(len(StubUpstream.observed), 1)
        method, path, forwarded_body, headers = StubUpstream.observed[0]
        self.assertEqual((method, path), ("POST", "/v1/responses"))
        self.assertEqual(json.loads(forwarded_body), {"model": "test-model"})
        self.assertEqual(headers["Authorization"], "Bearer upstream-secret")
        self.assertNotIn(b"upstream-secret", body)
        self.assertEqual(self.request("POST", "/v1/responses", b'{"model":"test-model"}')[0], 429)

    def test_denies_wrong_route_model_and_expired_gateway(self) -> None:
        self.assertEqual(self.request("GET", "/v1/models")[0], 404)
        self.assertEqual(self.request("POST", "/v1/other", b"{}")[0], 404)
        self.assertEqual(self.request("POST", "/v1/responses", b'{"model":"other"}')[0], 403)
        self.assertEqual(self.server.request_count, 0)
        self.server.deadline = time.monotonic() - 1
        self.assertEqual(self.request("POST", "/v1/responses", b'{"model":"test-model"}')[0], 429)
        self.assertEqual(StubUpstream.observed, [])

    def test_health_never_exposes_key(self) -> None:
        status, body = self.request("GET", "/healthz")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"status": "ready"})
        self.assertNotIn(b"upstream-secret", body)


@unittest.skipUnless(shutil.which("codex"), "Codex CLI not installed")
class CodexWireTests(unittest.TestCase):
    def test_custom_provider_routes_to_keyless_gateway(self) -> None:
        seen: list[str] = []

        class RejectingHandler(gateway.BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802 - stdlib HTTP handler hook
                seen.append(self.path)
                body = b'{"error":{"message":"intentional test rejection"}}'
                self.send_response(401)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: object) -> None:
                pass

        server = gateway.ThreadingHTTPServer(("127.0.0.1", 0), RejectingHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                env = {
                    key: value
                    for key, value in os.environ.items()
                    if key not in {"CODEX_API_KEY", "OPENAI_API_KEY", "CODEX_ACCESS_TOKEN"}
                }
                env["HOME"] = directory
                env["CODEX_HOME"] = directory
                result = subprocess.run(
                    [
                        "codex",
                        "exec",
                        "--ignore-user-config",
                        "--ephemeral",
                        "--skip-git-repo-check",
                        "--sandbox",
                        "read-only",
                        "--model",
                        "gpt-5.1-codex-mini",
                        "-c",
                        'model_provider="harnessflow_gateway"',
                        "-c",
                        'model_providers.harnessflow_gateway.name="HarnessFlow gateway"',
                        "-c",
                        f'model_providers.harnessflow_gateway.base_url="http://127.0.0.1:{server.server_port}/v1"',
                        "-c",
                        'model_providers.harnessflow_gateway.wire_api="responses"',
                        "-c",
                        "model_providers.harnessflow_gateway.requires_openai_auth=false",
                        "-c",
                        "model_providers.harnessflow_gateway.request_max_retries=0",
                        "-c",
                        "model_providers.harnessflow_gateway.stream_max_retries=0",
                        "-c",
                        'web_search="disabled"',
                        "Say hi.",
                    ],
                    env=env,
                    cwd=directory,
                    capture_output=True,
                    text=True,
                    timeout=20,
                    check=False,
                )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("/v1/responses", seen, result.stderr[-1000:])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
