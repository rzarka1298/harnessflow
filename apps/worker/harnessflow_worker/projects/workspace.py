"""Repository changes are confined to an owned worktree and branch."""

from __future__ import annotations

import hashlib
from pathlib import Path

from harnessflow_worker.projects.process import run_process


class Workspace:
    def __init__(self, repository: Path, data_dir: Path, run_id: str, lock_fd: int) -> None:
        self.repository = repository.resolve(strict=True)
        self.root = data_dir / "runs" / run_id
        self.path = self.root / "workspace"
        self.branch = f"harnessflow/{run_id}"
        self.lock_fd = lock_fd
        self.root.mkdir(parents=True, exist_ok=True)

    async def git(self, *args: str, cwd: Path | None = None, stdin: str | None = None) -> str:
        result = await run_process(
            [
                "git",
                "-c",
                "core.fsmonitor=false",
                "-c",
                "core.hooksPath=/dev/null",
                "-c",
                "commit.gpgsign=false",
                "-c",
                "user.name=HarnessFlow",
                "-c",
                "user.email=harnessflow@localhost",
                *args,
            ],
            cwd or self.path,
            stdin=stdin,
            lock_fd=self.lock_fd,
        )
        if result.exit_code:
            raise RuntimeError(f"git {args[0]}: {result.stderr[-2000:]}")
        return result.stdout.strip()

    async def prepare(self) -> str:
        base_file = self.root / "base-commit"
        if self.path.exists():
            actual = await self.git("rev-parse", "--show-toplevel")
            if Path(actual).resolve() != self.path.resolve():
                raise RuntimeError("existing workspace is not the owned worktree")
            if await self.git("branch", "--show-current") != self.branch:
                raise RuntimeError("owned workspace branch was changed externally")
            if not base_file.is_file():
                raise RuntimeError("workspace is missing its base checkpoint")
            return base_file.read_text().strip()
        try:
            base = await self.git("rev-parse", "--verify", "HEAD", cwd=self.repository)
        except RuntimeError:
            # An unborn repository gets a root commit in the object database only.
            # Its index, files and current branch remain exactly as the user left them.
            tree = await self.git("mktree", cwd=self.repository, stdin="")
            base = await self.git(
                "commit-tree", tree, "-m", "HarnessFlow empty base", cwd=self.repository
            )
        if base_file.exists():
            base = base_file.read_text().strip()
        else:
            base_file.write_text(base + "\n")
        refs = await self.git(
            "for-each-ref", "--format=%(refname)", f"refs/heads/{self.branch}", cwd=self.repository
        )
        if refs:
            await self.git("worktree", "add", str(self.path), self.branch, cwd=self.repository)
        else:
            await self.git(
                "worktree", "add", "-b", self.branch, str(self.path), base, cwd=self.repository
            )
        return base

    async def checkpoint(self, message: str) -> str:
        if await self.git("status", "--porcelain"):
            await self.git("add", "--all")
            await self.git("commit", "-m", message)
        return await self.git("rev-parse", "HEAD")

    async def fingerprint(self) -> str:
        # Includes untracked content through the index only after checkpointing.
        return await self.git("rev-parse", "HEAD^{tree}")

    async def diff(self, base: str) -> str:
        return await self.git("diff", "--no-ext-diff", "--no-textconv", base, "HEAD", "--")


def repository_lock_name(repository: str) -> str:
    return hashlib.sha256(str(Path(repository).resolve()).encode()).hexdigest()
