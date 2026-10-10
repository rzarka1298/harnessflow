"""Real subprocess lifecycle tests, including abrupt worker death."""

from __future__ import annotations

import asyncio
import contextlib
import fcntl
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from harnessflow_worker.projects.process import RunInterruptedError, run_process


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
