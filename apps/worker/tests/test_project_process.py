"""Real subprocess lifecycle tests, including abrupt worker death."""

from __future__ import annotations

import asyncio
import contextlib
import fcntl
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from harnessflow_worker.projects.agent import CodexAgent
from harnessflow_worker.projects.process import (
    Result,
    RunInterruptedError,
    process_environment,
    run_process,
)


@pytest.mark.asyncio
async def test_repository_commands_do_not_inherit_model_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CODEX_API_KEY", "codex-test-secret")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-secret")
    result = await run_process(
        [
            sys.executable,
            "-c",
            "import json,os;print(json.dumps({k:os.environ.get(k) for k in "
            "('CODEX_API_KEY','OPENAI_API_KEY')}))",
        ],
        tmp_path,
    )
    assert result.exit_code == 0
    assert result.stdout.strip() == '{"CODEX_API_KEY": null, "OPENAI_API_KEY": null}'
    codex_env = process_environment(include_model_credentials=True)
    assert codex_env["CODEX_API_KEY"] == "codex-test-secret"
    assert "OPENAI_API_KEY" not in codex_env
    monkeypatch.delenv("CODEX_API_KEY")
    assert process_environment(include_model_credentials=True)["OPENAI_API_KEY"] == (
        "openai-test-secret"
    )


@pytest.mark.asyncio
async def test_only_model_attempt_receives_model_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Answer(BaseModel):
        ok: bool

    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    workspace = SimpleNamespace(root=tmp_path, path=workspace_path, lock_fd=None)
    agent = CodexAgent(workspace)
    monkeypatch.setenv("CODEX_API_KEY", "codex-test-secret")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-secret")
    observed: list[dict[str, str]] = []

    async def fake_run_process(argv: list[str], cwd: Path, **kwargs: object) -> Result:
        assert argv[:2] == [agent.binary, "exec"]
        assert cwd == workspace_path
        env = kwargs["env"]
        assert isinstance(env, dict)
        observed.append(env)
        output = Path(argv[argv.index("--output-last-message") + 1])
        output.write_text(json.dumps({"ok": True}))
        return Result(0, "", "")

    async def poll() -> None:
        return None

    monkeypatch.setattr("harnessflow_worker.projects.agent.run_process", fake_run_process)
    answer, _ = await agent.run("test", Answer, "credential-test", poll, 10)
    assert answer == {"ok": True}
    assert observed[0]["CODEX_API_KEY"] == "codex-test-secret"
    assert "OPENAI_API_KEY" not in observed[0]


@pytest.mark.asyncio
async def test_gateway_model_attempt_uses_empty_home_and_no_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Answer(BaseModel):
        ok: bool

    monkeypatch.setenv("HARNESSFLOW_CODEX_GATEWAY_URL", "http://127.0.0.1:8765/v1")
    monkeypatch.delenv("CODEX_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    workspace = SimpleNamespace(root=tmp_path, path=workspace_path, lock_fd=None)
    agent = CodexAgent(workspace)
    observed: list[tuple[list[str], dict[str, str]]] = []

    async def fake_run_process(argv: list[str], cwd: Path, **kwargs: object) -> Result:
        env = kwargs["env"]
        assert isinstance(env, dict)
        observed.append((argv, env))
        Path(argv[argv.index("--output-last-message") + 1]).write_text('{"ok":true}')
        return Result(0, "", "")

    async def poll() -> None:
        return None

    monkeypatch.setattr("harnessflow_worker.projects.agent.run_process", fake_run_process)
    answer, _ = await agent.run("test", Answer, "gateway-test", poll, 10)
    assert answer == {"ok": True}
    argv, env = observed[0]
    assert 'model_provider="harnessflow_gateway"' in argv
    assert 'model_providers.harnessflow_gateway.base_url="http://127.0.0.1:8765/v1"' in argv
    assert env["HOME"] == str(tmp_path / "codex-home")
    assert env["CODEX_HOME"] == env["HOME"]
    assert "CODEX_API_KEY" not in env and "OPENAI_API_KEY" not in env


def test_gateway_mode_rejects_model_key_and_non_loopback_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = SimpleNamespace(root=tmp_path, path=tmp_path, lock_fd=None)
    monkeypatch.setenv("HARNESSFLOW_CODEX_GATEWAY_URL", "http://example.com/v1")
    with pytest.raises(ValueError, match=r"127\.0\.0\.1"):
        CodexAgent(workspace)
    monkeypatch.setenv("HARNESSFLOW_CODEX_GATEWAY_URL", "http://127.0.0.1:8765/v1")
    monkeypatch.setenv("CODEX_API_KEY", "should-not-reach-worker")
    with pytest.raises(ValueError, match="must not receive"):
        CodexAgent(workspace)


def sleeping_command(marker: Path) -> list[str]:
    return [
        sys.executable,
        "-c",
        "import os,time;from pathlib import Path;"
        f"Path({str(marker)!r}).write_text(str(os.getpid()));time.sleep(60)",
    ]


@pytest.mark.asyncio
async def test_cancel_while_command_does_not_read_large_input(tmp_path: Path) -> None:
    marker = tmp_path / "child.pid"

    async def cancel_when_started() -> None:
        if marker.exists():
            raise RunInterruptedError("cancel")

    with pytest.raises(RunInterruptedError, match="cancel"):
        await asyncio.wait_for(
            run_process(
                sleeping_command(marker),
                tmp_path,
                timeout=10,
                stdin="x" * 1_000_000,
                poll=cancel_when_started,
            ),
            3,
        )


def running(pid: int) -> bool:
    result = subprocess.run(
        ["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True, check=False
    )
    return bool(result.stdout.strip()) and not result.stdout.strip().startswith("Z")


@pytest.mark.asyncio
async def test_timeout_kills_command_and_descendant(tmp_path: Path) -> None:
    marker = tmp_path / "grandchild.pid"
    argv = [
        sys.executable,
        "-c",
        f"import subprocess,sys,time;subprocess.Popen({sleeping_command(marker)!r});time.sleep(60)",
    ]
    result = await run_process(argv, tmp_path, timeout=0.5)
    assert result.exit_code == 124
    assert marker.exists()
    assert not running(int(marker.read_text()))


@pytest.mark.asyncio
async def test_activity_cancellation_kills_process(tmp_path: Path) -> None:
    marker = tmp_path / "child.pid"
    task = asyncio.create_task(run_process(sleeping_command(marker), tmp_path))
    try:
        async with asyncio.timeout(3):
            while not marker.exists():
                await asyncio.sleep(0.02)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not running(int(marker.read_text()))
    finally:
        if not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


@pytest.mark.asyncio
async def test_normal_exit_cleans_background_child(tmp_path: Path) -> None:
    marker = tmp_path / "background.pid"
    argv = [
        sys.executable,
        "-c",
        f"import subprocess,time;subprocess.Popen({sleeping_command(marker)!r});time.sleep(0.2)",
    ]
    result = await run_process(argv, tmp_path)
    assert result.exit_code == 0
    assert marker.exists()
    assert not running(int(marker.read_text()))


def test_worker_sigkill_kills_descendants_and_releases_lock(tmp_path: Path) -> None:
    marker = tmp_path / "grandchild.pid"
    child_marker = tmp_path / "child.pid"
    lock_path = tmp_path / "repository.lock"
    argv = [
        sys.executable,
        "-c",
        "import os,subprocess,time;from pathlib import Path;"
        f"Path({str(child_marker)!r}).write_text(str(os.getpid()));"
        f"subprocess.Popen({sleeping_command(marker)!r});time.sleep(60)",
    ]
    worker_code = (
        "import asyncio,fcntl;from pathlib import Path;"
        "from harnessflow_worker.projects.process import run_process;"
        f"lock=open({str(lock_path)!r},'a');fcntl.flock(lock,fcntl.LOCK_EX);"
        f"asyncio.run(run_process({argv!r},Path({str(tmp_path)!r}),lock_fd=lock.fileno()))"
    )
    worker = subprocess.Popen(
        [sys.executable, "-c", worker_code], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    try:
        deadline = time.monotonic() + 5
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert marker.exists(), "command did not start"
        worker.kill()
        worker.wait(timeout=3)
        with lock_path.open("a") as lock:
            while time.monotonic() < deadline:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    time.sleep(0.02)
            else:
                pytest.fail("orphan process retained the repository lock")
        assert not running(int(child_marker.read_text()))
        assert not running(int(marker.read_text()))
    finally:
        if worker.poll() is None:
            worker.kill()
            worker.wait(timeout=3)
        if child_marker.exists():
            with contextlib.suppress(ProcessLookupError):
                os.killpg(int(child_marker.read_text()), signal.SIGKILL)


@pytest.mark.asyncio
async def test_detached_daemon_cannot_inherit_repository_lock(tmp_path: Path) -> None:
    marker = tmp_path / "daemon.pid"
    lock_path = tmp_path / "repository.lock"
    code = f"""
import os,time
from pathlib import Path
marker = Path({str(marker)!r})
if os.fork():
    deadline = time.monotonic() + 2
    while not marker.exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    os._exit(0 if marker.exists() else 1)
os.setsid()
if os.fork():
    os._exit(0)
null = os.open(os.devnull, os.O_RDWR)
for fd in (0, 1, 2):
    os.dup2(null, fd)
os.close(null)
marker.write_text(str(os.getpid()))
time.sleep(60)
"""
    try:
        with lock_path.open("a") as owned:
            fcntl.flock(owned, fcntl.LOCK_EX)
            result = await run_process(
                [sys.executable, "-c", code], tmp_path, timeout=5, lock_fd=owned.fileno()
            )
            assert result.exit_code == 0
        assert marker.exists()
        assert running(int(marker.read_text())), "test daemon must survive process-group cleanup"
        with lock_path.open("a") as next_owner:
            try:
                fcntl.flock(next_owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                pytest.fail("detached daemon inherited the repository lock")
    finally:
        if marker.exists():
            with contextlib.suppress(ProcessLookupError):
                os.kill(int(marker.read_text()), signal.SIGKILL)


@pytest.mark.asyncio
async def test_descendant_git_disables_fsmonitor(tmp_path: Path) -> None:
    result = await run_process(["git", "config", "--get", "core.fsmonitor"], tmp_path)
    assert result.exit_code == 0
    assert result.stdout.strip() == "false"
