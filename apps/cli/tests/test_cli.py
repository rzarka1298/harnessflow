from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

import harnessflow_cli as cli


class FakeAPI(BaseHTTPRequestHandler):
    calls: ClassVar[list[tuple[str, dict]]] = []
    fail = False
    get_status = "running"

    def do_POST(self) -> None:
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).calls.append((self.path, payload))
        if type(self).fail:
            body, status = {"code": "invalid_argument", "message": "bad PRD"}, 400
        elif self.path.endswith("/CreateProject"):
            body, status = {"project": {"id": "project-id"}}, 200
        elif self.path.endswith("/StartRun"):
            body, status = {"run": {"id": "run-id", "status": "queued"}}, 200
        elif self.path.endswith("/GetRun"):
            body, status = (
                {
                    "run": {
                        "id": payload["id"],
                        "projectId": "project-id",
                        "status": type(self).get_status,
                        "snapshotJson": json.dumps({"phase": "judge", "head_commit": "abc"}),
                    }
                },
                200,
            )
        else:
            body, status = {"run": {"id": payload["runId"], "status": "running"}}, 200
        encoded = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, *_: object) -> None:
        pass


class CLITests(unittest.TestCase):
    def setUp(self) -> None:
        FakeAPI.calls = []
        FakeAPI.fail = False
        FakeAPI.get_status = "running"
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), FakeAPI)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.api = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()

    def test_run_with_spaces_in_prd_and_unborn_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "workspace with spaces"
            repo.mkdir()
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
            prd = repo / "Product Requirements.md"
            prd.write_text("Build a useful thing.", encoding="utf-8")
            args = cli.build_parser().parse_args(
                [
                    "--api",
                    self.api,
                    "run",
                    "Product Requirements.md",
                    "--repo",
                    str(repo),
                    "--max-attempts",
                    "7",
                    "--max-duration-seconds",
                    "900",
                    "--model",
                    "codex-test",
                ]
            )
            with patch("pathlib.Path.cwd", return_value=repo):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(cli._run(args), 0)
            emitted = json.loads(output.getvalue())
            self.assertEqual(emitted["run_id"], "run-id")
            self.assertIn("/projects/project-id/runs/run-id", emitted["dashboard_url"])
            create_path, create = FakeAPI.calls[0]
            self.assertTrue(create_path.endswith("/CreateProject"))
            self.assertEqual(create["repositoryPath"], str(repo.resolve()))
            self.assertEqual(create["prd"], "Build a useful thing.")
            self.assertTrue(FakeAPI.calls[1][0].endswith("/StartRun"))
            self.assertEqual(
                FakeAPI.calls[1][1],
                {
                    "projectId": "project-id",
                    "maxAttempts": 7,
                    "maxDurationSeconds": 900,
                    "model": "codex-test",
                },
            )

    def test_run_rejects_nonpositive_limits(self) -> None:
        with self.assertRaises(SystemExit):
            cli.build_parser().parse_args(["run", "prd.md", "--max-attempts", "0"])

    def test_wait_stops_on_resumable_blocker(self) -> None:
        FakeAPI.get_status = "blocked"
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
            (repo / "prd.md").write_text("Build a thing", encoding="utf-8")
            args = cli.build_parser().parse_args(
                ["--api", self.api, "run", "prd.md", "--repo", str(repo), "--wait"]
            )
            with (
                patch("pathlib.Path.cwd", return_value=repo),
                patch("time.sleep"),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(cli._run(args), 1)
        self.assertEqual(sum(path.endswith("/GetRun") for path, _ in FakeAPI.calls), 1)

    def test_status_is_concise_unless_full_requested(self) -> None:
        args = cli.build_parser().parse_args(["--api", self.api, "status", "run-id"])
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(cli._status(args), 0)
        value = json.loads(output.getvalue())
        self.assertEqual(value["phase"], "judge")
        self.assertEqual(value["commit"], "abc")
        self.assertEqual(
            value["dashboard_url"],
            "http://127.0.0.1:3001/projects/project-id/runs/run-id",
        )
        self.assertNotIn("snapshotJson", value)
        args = cli.build_parser().parse_args(["--api", self.api, "status", "run-id", "--full"])
        with contextlib.redirect_stdout(output := io.StringIO()):
            self.assertEqual(cli._status(args), 0)
        self.assertIn("snapshotJson", json.loads(output.getvalue()))

    def test_relative_prd_can_be_resolved_from_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
            (repo / "spec.md").write_text("spec", encoding="utf-8")
            with patch("pathlib.Path.cwd", return_value=Path(temp)):
                self.assertEqual(
                    cli._resolve_prd("spec.md", repo.resolve()),
                    (repo / "spec.md").resolve(),
                )

    def test_connect_api_error_is_actionable(self) -> None:
        FakeAPI.fail = True
        with self.assertRaisesRegex(
            cli.CLIError, "API CreateProject failed \(invalid_argument\): bad PRD"
        ):
            cli._api_call(self.api, "CreateProject", {"name": "x"})

    def test_run_rejects_relative_path_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            repo = root / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
            outside = root / "secret.md"
            outside.write_text("secret", encoding="utf-8")
            with (
                patch("pathlib.Path.cwd", return_value=repo),
                self.assertRaisesRegex(cli.CLIError, "PRD file not found|Relative PRD paths"),
            ):
                cli._resolve_prd("../secret.md", repo.resolve())


if __name__ == "__main__":
    unittest.main()
