"""Bounded process groups with cancellation, output limits and explicit environments."""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path


class RunInterruptedError(Exception):
    """A durable control request interrupted the current attempt."""

    def __init__(self, action: str) -> None:
        self.action = action
        super().__init__(action)


@dataclass
class Result:
    exit_code: int
    stdout: str
    stderr: str


def process_environment() -> dict[str, str]:
    """Only credentials intentionally needed by Codex are inherited."""
    names = {
        "PATH",
        "HOME",
        "USER",
        "TMPDIR",
        "LANG",
        "LC_ALL",
        "CODEX_HOME",
        "CODEX_API_KEY",
        "OPENAI_API_KEY",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
    }
    env = {key: value for key, value in os.environ.items() if key in names}
    env.update({"GIT_TERMINAL_PROMPT": "0", "NO_COLOR": "1"})
    # A user's global fsmonitor setting can launch a detached Git daemon.
    # Disable it in all descendant Git invocations, including agent tool calls.
    env.update(
        {
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "core.fsmonitor",
            "GIT_CONFIG_VALUE_0": "false",
        }
    )
    return env


async def run_process(
    argv: list[str],
    cwd: Path,
    timeout: float = 60,
    poll: Callable[[], Awaitable[None]] | None = None,
    stdin: str | None = None,
    lock_fd: int | None = None,
    log_path: Path | None = None,
    env: dict[str, str] | None = None,
) -> Result:
    """Run argv directly. The watchdog terminates descendants after parent death."""
    if timeout <= 0:
        raise RunInterruptedError("exhausted")
    if poll:
        await poll()
    command = [
        sys.executable,
        str(Path(__file__).with_name("watchdog.py")),
        str(os.getpid()),
        str(timeout),
        *argv,
    ]
    proc = await asyncio.create_subprocess_exec(
        *command,
        cwd=cwd,
        env=env or process_environment(),
        stdin=asyncio.subprocess.PIPE if stdin is not None else asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
        pass_fds=() if lock_fd is None else (lock_fd,),
    )
    output_limit = 1_000_000

    async def read(stream: asyncio.StreamReader | None) -> str:
        assert stream is not None
        chunks = bytearray()
        while chunk := await stream.read(8192):
            if log_path:
                with log_path.open("ab") as log:
                    # Bound the on-disk artifact too; noisy commands cannot fill the disk.
                    if log.tell() < 10_000_000:
                        log.write(chunk)
            remaining = output_limit - len(chunks)
            if remaining > 0:
                chunks.extend(chunk[:remaining])
        return chunks.decode("utf-8", errors="replace")

    readers = [asyncio.create_task(read(proc.stdout)), asyncio.create_task(read(proc.stderr))]

    async def feed_input() -> None:
        if stdin is not None and proc.stdin:
            try:
                proc.stdin.write(stdin.encode())
                await proc.stdin.drain()
            except (BrokenPipeError, ConnectionResetError):
                # Commands may exit without consuming the complete prompt.
                pass
            finally:
                proc.stdin.close()

    # Input pipes apply backpressure too. Feeding them inline would prevent
    # control polling when a command does not consume a large prompt.
    feeding = asyncio.create_task(feed_input())
    try:
        while proc.returncode is None:
            try:
                await asyncio.wait_for(proc.wait(), timeout=1)
            except TimeoutError:
                if poll:
                    await poll()
        stdout, stderr = await asyncio.gather(*readers)
        await feeding
        return Result(proc.returncode, stdout, stderr)
    finally:
        # Kill the whole group even if the main command already exited. Test servers
        # and grandchildren must not outlive their attempt or hold the repository lock.
        with contextlib.suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGTERM)
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(proc.wait(), 3)
        with contextlib.suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGKILL)
        await proc.wait()
        for reader in [*readers, feeding]:
            if not reader.done():
                reader.cancel()
        await asyncio.gather(*readers, feeding, return_exceptions=True)
