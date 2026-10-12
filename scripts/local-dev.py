#!/usr/bin/env python3
"""Run the local stack; own only the host process groups started here."""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".local" / "harnessflow"
PYTHON_APPS = ("worker", "eval-runner", "event-consumer")


def environment() -> dict[str, str]:
    """Read literal dotenv values, without executing or expanding shell code."""
    env = dict(os.environ)
    path = ROOT / ".env"
    if path.exists():
        for number, raw in enumerate(path.read_text().splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            key, separator, value = line.partition("=")
            key, value = key.strip(), value.strip()
            if not separator or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
                raise ValueError(f".env:{number}: expected NAME=literal-value")
            if value.startswith(("'", '"')):
                if len(value) < 2 or value[-1] != value[0]:
                    raise ValueError(f".env:{number}: unmatched quotes")
                value = value[1:-1]
            env.setdefault(key, value)
    defaults = {
        "DATABASE_URL": "postgres://harnessflow:harnessflow@127.0.0.1:5432/harnessflow?sslmode=disable",
        "TEMPORAL_HOST": "127.0.0.1:7233",
        "API_HOST": "127.0.0.1",
        "API_PORT": "8080",
        "OTEL_EXPORTER_OTLP_ENDPOINT_GRPC": "",
        "HARNESSFLOW_EVENTS_BROKERS": "",
    }
    for key, value in defaults.items():
        env.setdefault(key, value)
    # These services are local-only; never inherit a public listen address.
    env["API_HOST"] = "127.0.0.1"
    env["DASHBOARD_ORIGIN"] = "http://127.0.0.1:3001"
    env["NEXT_PUBLIC_API_BASE_URL"] = f"http://127.0.0.1:{env['API_PORT']}"
    return env


def run(args: list[str], env: dict[str, str], cwd: Path = ROOT) -> None:
    print(">> " + " ".join(args[:4]), flush=True)
    subprocess.run(args, cwd=cwd, env=env, check=True)


def check_port_available(port: int) -> None:
    with socket.socket() as sock:
        # Match server restart semantics: ignore closed connections in TIME_WAIT,
        # while still rejecting a live listener (do not enable SO_REUSEPORT).
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError as exc:
            raise RuntimeError(f"Port {port} is already occupied; stop its server first") from exc


def preflight(env: dict[str, str], mock: bool = False) -> None:
    tools = ["docker", "go", "uv", "pnpm", "migrate", "git"]
    if not mock:
        tools.append(env.get("HARNESSFLOW_CODEX_BIN", "codex"))
    missing = [tool for tool in tools if not shutil.which(tool)]
    if missing:
        raise RuntimeError("Missing tools: " + ", ".join(missing) + "; see README prerequisites")
    port = int(env["API_PORT"])
    for value in (port, 3001):
        check_port_available(value)
    subprocess.run(
        ["docker", "compose", "version"],
        cwd=ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    if not mock and not env.get("HARNESSFLOW_CODEX_GATEWAY_URL"):
        subprocess.run(
            [env.get("HARNESSFLOW_CODEX_BIN", "codex"), "login", "status"],
            env=env,
            check=True,
        )


class Processes:
    def __init__(self, env: dict[str, str]) -> None:
        self.env = env
        self.children: list[tuple[str, subprocess.Popen[bytes]]] = []

    def start(self, name: str, args: list[str], cwd: Path) -> None:
        path = STATE / f"{name}.log"
        with path.open("wb") as log:
            process = subprocess.Popen(
                args,
                cwd=cwd,
                env=self.env,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        self.children.append((name, process))
        print(f">> {name}: {path}", flush=True)

    def check(self) -> None:
        for name, process in self.children:
            if process.poll() is not None:
                raise RuntimeError(
                    f"{name} exited ({process.returncode}); inspect {STATE / (name + '.log')}"
                )

    def wait_http(self, url: str, timeout: int = 120) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.check()
            try:
                with urllib.request.urlopen(url, timeout=2) as response:
                    if response.status == 200:
                        return
            except (urllib.error.URLError, TimeoutError):
                pass
            time.sleep(0.5)
        raise RuntimeError(f"Timed out waiting for {url}; inspect logs in {STATE}")

    def wait_worker(self, timeout: int = 120) -> None:
        deadline = time.monotonic() + timeout
        path = STATE / "worker.log"
        while time.monotonic() < deadline:
            self.check()
            if "worker started" in path.read_text(errors="replace"):
                return
            time.sleep(0.5)
        raise RuntimeError(f"Worker startup exceeded {timeout} seconds; inspect {path}")

    def close(self) -> None:
        # Signal complete groups even if their leader exited (e.g. pnpm -> next).
        for _, process in reversed(self.children):
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGTERM)
        deadline = time.monotonic() + 5
        for _, process in self.children:
            with contextlib.suppress(subprocess.TimeoutExpired):
                process.wait(timeout=max(0.01, deadline - time.monotonic()))
        for _, process in reversed(self.children):
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            process.wait()


def demo(processes: Processes, env: dict[str, str]) -> None:
    base = env["NEXT_PUBLIC_API_BASE_URL"]

    def rpc(service: str, method: str, body: dict[str, object]) -> dict:
        request = urllib.request.Request(
            f"{base}/harnessflow.{service}/{method}",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.load(response)

    source = (ROOT / "packages/examples/workflows/research-assistant.yaml").read_text()
    source = source.replace(
        "name: research-assistant",
        f"name: research-assistant-{uuid.uuid4().hex[:8]}",
        1,
    )
    workflow = rpc("workflow.v1.WorkflowService", "CreateWorkflow", {"yamlSource": source})
    result = rpc(
        "workflow.v1.WorkflowService",
        "RunWorkflow",
        {
            "workflowId": workflow["workflow"]["id"],
            "inputs": {"query": "How does Temporal handle workflow retries vs activity retries?"},
        },
    )
    run_id = result["runId"]
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        processes.check()
        result = rpc("run.v1.RunService", "GetRun", {"id": run_id})
        status = result["run"]["status"]
        if status in ("RUN_STATUS_COMPLETED", 3):
            print(json.dumps(result, indent=2))
            print(f"Demo completed: {run_id}. Run make dev to browse persisted results.")
            return
        if status in ("RUN_STATUS_FAILED", "RUN_STATUS_CANCELED", 4, 6):
            raise RuntimeError(f"Demo ended with {status}: {run_id}")
        time.sleep(1)
    raise RuntimeError(f"Demo exceeded 180 seconds: {run_id}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-install", action="store_true", help="reuse installed dependencies")
    parser.add_argument("--check", action="store_true", help="validate configuration/tooling only")
    parser.add_argument(
        "--demo", action="store_true", help="run a bounded mock workflow smoke test"
    )
    args = parser.parse_args()
    env = environment()
    preflight(env, mock=args.demo)
    if args.check:
        print("Local prerequisites and ports are ready.")
        return 0
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE / "launcher.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Another local launcher is already running") from exc
        if args.demo:
            env["HARNESSFLOW_MOCK"] = "1"
            env["OPENAI_API_KEY"] = ""
            env["ANTHROPIC_API_KEY"] = ""
        if not args.skip_install:
            for app in PYTHON_APPS:
                run(["uv", "sync", "--frozen", "--directory", f"apps/{app}"], env)
            run(["pnpm", "install", "--frozen-lockfile"], env, ROOT / "apps/dashboard")
        run(
            [
                "docker",
                "compose",
                "up",
                "-d",
                "--wait",
                "--wait-timeout",
                "180",
                "postgres",
                "temporal",
            ],
            env,
        )
        # Never print the database URL, which can contain credentials.
        migration = subprocess.run(
            [
                "migrate",
                "-path",
                "apps/api/migrations",
                "-database",
                env["DATABASE_URL"],
                "up",
            ],
            cwd=ROOT,
            env=env,
        )
        if migration.returncode:
            raise RuntimeError("Database migration failed; check the migration output above")
        run(["go", "build", "-o", str(STATE / "api"), "./apps/api/cmd/api"], env)
        if args.demo:
            run(
                [
                    str(ROOT / "apps/worker/.venv/bin/python"),
                    str(ROOT / "scripts/seed-chroma.py"),
                ],
                env,
                ROOT / "apps/worker",
            )
        processes = Processes(env)
        try:
            processes.start("api", [str(STATE / "api")], ROOT)
            processes.start(
                "worker",
                [
                    str(ROOT / "apps/worker/.venv/bin/python"),
                    "-m",
                    "harnessflow_worker",
                ],
                ROOT / "apps/worker",
            )
            processes.wait_http(f"{env['NEXT_PUBLIC_API_BASE_URL']}/readyz")
            processes.wait_worker()
            if args.demo:
                demo(processes, env)
            else:
                processes.start(
                    "dashboard",
                    [
                        str(ROOT / "apps/dashboard/node_modules/.bin/next"),
                        "dev",
                        "--hostname",
                        "127.0.0.1",
                        "--port",
                        "3001",
                    ],
                    ROOT / "apps/dashboard",
                )
                processes.wait_http("http://127.0.0.1:3001")
                print(
                    "\nHarnessFlow: http://127.0.0.1:3001\n"
                    "Ctrl-C stops these apps; make down stops infrastructure.\n",
                    flush=True,
                )
                while True:
                    processes.check()
                    time.sleep(1)
        finally:
            processes.close()
    return 0


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(
            "\nStopped local apps. Database and Temporal remain available; "
            "use make down to stop them."
        )
        sys.exit(130)
    except (ValueError, RuntimeError, subprocess.CalledProcessError, OSError) as error:
        print(f"local-dev: {error}", file=sys.stderr)
        sys.exit(1)
