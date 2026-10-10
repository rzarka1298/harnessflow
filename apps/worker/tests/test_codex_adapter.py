"""Opt-in native Codex CLI boundary tests; no model calls or credentials read.

Run with HARNESSFLOW_TEST_CODEX_SANDBOX=1. Fixtures deliberately live outside
system temp directories, which the built-in :workspace profile permits writing.
"""

from __future__ import annotations

import fcntl
import json
import os
import socket
import subprocess
import sys
import tempfile
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from harnessflow_worker.projects.agent import CodexAgent
from harnessflow_worker.projects.process import Result
from harnessflow_worker.projects.workspace import Workspace

pytestmark = pytest.mark.skipif(
    os.environ.get("HARNESSFLOW_TEST_CODEX_SANDBOX") != "1",
    reason="set HARNESSFLOW_TEST_CODEX_SANDBOX=1 to exercise the native CLI sandbox",
)


async def poll() -> None:
    pass


@pytest.fixture
async def adapter() -> AsyncIterator[CodexAgent]:
    parent = Path(__file__).resolve().parents[3] / ".local" / "codex-sandbox-tests"
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="owned-", dir=parent) as directory:
        root = Path(directory)
        repository = root / "original"
        repository.mkdir()
        subprocess.run(
            ["git", "-c", "core.fsmonitor=false", "init", "-q", str(repository)], check=True
        )
        with (root / "repository.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            work = Workspace(repository, root / "data", str(uuid.uuid4()), lock.fileno())
            await work.prepare()
            yield CodexAgent(work)


async def command(adapter: CodexAgent, code: str, *args: str) -> Result:
    return await adapter.verify_command(
        [sys.executable, "-c", code, *args], str(uuid.uuid4()), poll, 30
    )


@pytest.mark.asyncio
async def test_native_cli_preserves_exit_status_and_literal_arguments(adapter: CodexAgent) -> None:
    literal = "$(touch not-created); * 'quoted' $HOME"
    success = await command(adapter, "import json,sys;print(json.dumps(sys.argv[1:]))", literal)
    assert success.exit_code == 0, success.stderr
    assert json.loads(success.stdout) == [literal]
    assert not (adapter.workspace.path / "not-created").exists()
    failure = await command(adapter, "raise AssertionError('intentional acceptance failure')")
    assert failure.exit_code == 1, failure.stderr
    assert "intentional acceptance failure" in failure.stderr


@pytest.mark.asyncio
async def test_native_cli_allows_worktree_write(adapter: CodexAgent) -> None:
    target = adapter.workspace.path / "acceptance-output.txt"
    result = await command(
        adapter,
        "from pathlib import Path;import sys;Path(sys.argv[1]).write_text('allowed')",
        str(target),
    )
    assert result.exit_code == 0, result.stderr
    assert target.read_text() == "allowed"


@pytest.mark.asyncio
async def test_native_cli_denies_sibling_and_original_metadata_writes(adapter: CodexAgent) -> None:
    work = adapter.workspace
    targets = [
        work.root / "outside-worktree.txt",
        work.repository / "outside-original.txt",
        work.repository / ".git" / "harnessflow-sandbox-probe",
    ]
    for target in targets:
        result = await command(
            adapter,
            "from pathlib import Path;import sys;Path(sys.argv[1]).write_text('must be denied')",
            str(target),
        )
        assert result.exit_code != 0, f"sandbox allowed writing {target}"
        assert not target.exists(), f"sandbox wrote outside its worktree: {target}"


@pytest.mark.asyncio
async def test_native_cli_protects_worktree_git_pointer(adapter: CodexAgent) -> None:
    target = adapter.workspace.path / ".git"
    before = target.read_bytes()
    result = await command(
        adapter,
        "from pathlib import Path;import sys;"
        "p=Path(sys.argv[1]);p.write_bytes(p.read_bytes()+b'\\n')",
        str(target),
    )
    assert result.exit_code != 0, "sandbox allowed overwriting the worktree Git pointer"
    assert target.read_bytes() == before


@pytest.mark.asyncio
async def test_native_cli_blocks_network_to_reachable_loopback_listener(
    adapter: CodexAgent,
) -> None:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(4)
        port = listener.getsockname()[1]
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            pass  # Prove the endpoint is reachable outside the native sandbox.
        result = await command(
            adapter,
            "import socket,sys;socket.create_connection(('127.0.0.1',int(sys.argv[1])),timeout=2)",
            str(port),
        )
        assert result.exit_code != 0, "workspace sandbox allowed outbound loopback networking"
        assert "PermissionError" in result.stderr or "Operation not permitted" in result.stderr, (
            result.stderr
        )
