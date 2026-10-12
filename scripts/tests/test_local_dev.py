"""Configuration and ownership guarantees for the local launcher."""

import importlib.util
import os
import signal
import socket
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

SPEC = importlib.util.spec_from_file_location(
    "local_dev", Path(__file__).parents[1] / "local-dev.py"
)
assert SPEC and SPEC.loader
launcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launcher)


class EnvironmentTests(unittest.TestCase):
    def test_values_are_literal_and_process_environment_wins(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env").write_text(
                "# comment\nTOKEN='$(touch must-not-exist)'\nAPI_PORT=8000\nAPI_HOST=0.0.0.0\n"
            )
            with (
                patch.object(launcher, "ROOT", root),
                patch.dict(os.environ, {"API_PORT": "9000"}, clear=True),
            ):
                env = launcher.environment()
            self.assertEqual(env["TOKEN"], "$(touch must-not-exist)")
            self.assertEqual(env["API_PORT"], "9000")
            self.assertEqual(env["API_HOST"], "127.0.0.1")
            self.assertEqual(env["NEXT_PUBLIC_API_BASE_URL"], "http://127.0.0.1:9000")
            self.assertEqual(env["OTEL_EXPORTER_OTLP_ENDPOINT_GRPC"], "")
            self.assertFalse((root / "must-not-exist").exists())

    def test_rejects_shell_statements_and_unmatched_quotes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for value in ("export TOKEN=bad", "TOKEN='bad", "echo hello"):
                with self.subTest(value=value):
                    (root / ".env").write_text(value)
                    with (
                        patch.object(launcher, "ROOT", root),
                        self.assertRaises(ValueError),
                    ):
                        launcher.environment()


class ProcessTests(unittest.TestCase):
    def test_port_probe_accepts_recently_closed_server_connection(self):
        with socket.socket() as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            port = server.getsockname()[1]
            with socket.create_connection(("127.0.0.1", port), timeout=2) as client:
                connection, _ = server.accept()
                connection.close()
                # Server sends the first FIN, placing its endpoint in TIME_WAIT.
                self.assertEqual(client.recv(1), b"")
        launcher.check_port_available(port)

    def test_port_probe_still_rejects_active_listener(self):
        with socket.socket() as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            with self.assertRaisesRegex(RuntimeError, "already occupied"):
                launcher.check_port_available(server.getsockname()[1])

    def test_skip_install_launches_next_directly_without_package_manager(self):
        with tempfile.TemporaryDirectory() as directory:
            processes = MagicMock()
            processes.check.side_effect = KeyboardInterrupt
            env = {
                "DATABASE_URL": "postgres://local",
                "NEXT_PUBLIC_API_BASE_URL": "http://127.0.0.1:8080",
            }
            with (
                patch.object(launcher, "STATE", Path(directory)),
                patch.object(launcher.sys, "argv", ["local-dev.py", "--skip-install"]),
                patch.object(launcher, "environment", return_value=env),
                patch.object(launcher, "preflight"),
                patch.object(launcher, "run") as run,
                patch.object(launcher.subprocess, "run", return_value=MagicMock(returncode=0)),
                patch.object(launcher, "Processes", return_value=processes),
                self.assertRaises(KeyboardInterrupt),
            ):
                launcher.main()
            commands = [call.args[0] for call in run.call_args_list]
            self.assertFalse(any(command[0] in {"pnpm", "uv"} for command in commands))
            dashboard = next(
                call for call in processes.start.call_args_list if call.args[0] == "dashboard"
            )
            self.assertEqual(
                dashboard.args[1][0],
                str(launcher.ROOT / "apps/dashboard/node_modules/.bin/next"),
            )
            processes.close.assert_called_once()

    def test_failure_is_detected_even_with_zero_exit_code(self):
        processes = launcher.Processes({})
        child = MagicMock()
        child.poll.return_value = 0
        child.returncode = 0
        processes.children = [("worker", child)]
        with self.assertRaisesRegex(RuntimeError, "worker exited"):
            processes.check()

    def test_cleanup_signals_only_owned_groups_including_orphaned_children(self):
        processes = launcher.Processes({})
        child = MagicMock(pid=1234)
        child.wait.side_effect = [subprocess.TimeoutExpired("worker", 5), 0]
        processes.children = [("worker", child)]
        with patch.object(launcher.os, "killpg") as kill:
            processes.close()
        self.assertEqual(kill.call_args_list[0].args, (1234, signal.SIGTERM))
        self.assertEqual(kill.call_args_list[1].args, (1234, signal.SIGKILL))

    def test_health_wait_has_a_deadline(self):
        processes = launcher.Processes({})
        with self.assertRaisesRegex(RuntimeError, "Timed out"):
            processes.wait_http("http://127.0.0.1:1", timeout=0)


if __name__ == "__main__":
    unittest.main()
