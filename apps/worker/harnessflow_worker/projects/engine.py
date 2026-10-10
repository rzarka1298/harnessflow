"""One recoverable unit of project work per Temporal activity invocation."""

from __future__ import annotations

import fcntl
import json
import os
import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from harnessflow_worker.projects.agent import CodexAgent, context_prompt
from harnessflow_worker.projects.models import AgentResult, Plan, Review, completion_ready
from harnessflow_worker.projects.process import RunInterruptedError, run_process
from harnessflow_worker.projects.workspace import Workspace, repository_lock_name


class Store(Protocol):
    async def load(self) -> dict[str, Any]: ...
    async def save(self, state: dict[str, Any], status: str, reason: str = "") -> str: ...
    async def consume_control(self, control: str, version: int) -> None: ...


def now() -> str:
    return datetime.now(UTC).isoformat()


def event(state: dict[str, Any], message: str) -> None:
    state["events"] = [*state.get("events", []), {"at": now(), "message": message}][-200:]


async def tick(
    store: Store,
    data_dir: Path,
    heartbeat: Callable[[], None] = lambda: None,
    agent_factory: Callable[[Workspace, str], CodexAgent] = CodexAgent,
) -> dict[str, str]:
    row = await store.load()
    locks = data_dir / "locks"
    locks.mkdir(parents=True, exist_ok=True)
    with (locks / repository_lock_name(row["repository_path"])).open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"status": "running", "reason": "Waiting for the previous process to exit"}
        # No control or snapshot writes before exclusive ownership, including retries.
        row = await store.load()
        return await _locked_tick(store, row, data_dir, lock.fileno(), heartbeat, agent_factory)


async def _locked_tick(
    store: Store,
    row: dict[str, Any],
    data_dir: Path,
    lock_fd: int,
    heartbeat: Callable[[], None],
    agent_factory: Callable[[Workspace, str], CodexAgent],
) -> dict[str, str]:
    state: dict[str, Any] = row["state"]
    status = row["status"]
    if status in {"completed", "failed", "canceled"}:
        return {"status": status, "reason": row.get("reason", "")}
    action = row.get("control", "")
    if action in {"pause", "cancel"}:
        status = "paused" if action == "pause" else "canceled"
        await store.save(state, status, f"Run {status} by user")
        await store.consume_control(action, row.get("control_version", 0))
        return {"status": status, "reason": f"Run {status} by user"}
    if status in {"paused", "blocked", "exhausted"} and action != "resume":
        return {"status": status, "reason": row.get("reason", "")}
    if action == "resume":
        if row.get("clarification"):
            state["clarifications"] = [*state.get("clarifications", []), row["clarification"]]
        state["failure_count"] = 0
        state["repeated_failures"] = 0
        state.pop("last_failed_checks", None)
        event(state, "Resumed from the saved checkpoint")
        await store.save(state, "running")
        await store.consume_control(action, row.get("control_version", 0))

    return await _owned_tick(store, row, state, data_dir, lock_fd, heartbeat, agent_factory)


async def _owned_tick(
    store: Store,
    row: dict[str, Any],
    state: dict[str, Any],
    data_dir: Path,
    lock_fd: int,
    heartbeat: Callable[[], None],
    agent_factory: Callable[[Workspace, str], CodexAgent],
) -> dict[str, str]:
    start = time.monotonic()
    elapsed = float(state.get("active_seconds", 0))
    limit = int(row["max_duration_seconds"])
    status, reason = "running", ""
    phase = state.get("phase", "prepare")
    state.setdefault("attempts", 0)
    state.setdefault("completed_task_ids", [])
    state.setdefault("tokens", {"input": 0, "output": 0})
    state["cost_usd"] = None
    state["max_attempts"] = row["max_attempts"]
    state["max_duration_seconds"] = row["max_duration_seconds"]
    control_version = row.get("control_version", 0)
    consumed_action = ""

    async def poll() -> None:
        nonlocal control_version
        heartbeat()
        current = await store.load()
        if current["status"] in {"canceled", "failed"}:
            raise RunInterruptedError("cancel")
        action = current.get("control", "")
        if action in {"pause", "cancel"}:
            control_version = current.get("control_version", 0)
            raise RunInterruptedError(action)
        state["active_seconds"] = elapsed + time.monotonic() - start
        if state["active_seconds"] >= limit:
            raise RunInterruptedError("exhausted")
        await store.save(state, status)

    def remaining() -> float:
        return min(
            float(os.environ.get("HARNESSFLOW_AGENT_TIMEOUT_SECONDS", "1800")),
            limit - elapsed - (time.monotonic() - start),
        )

    async def ask(
        prompt: str, contract: type[Plan] | type[Review] | type[AgentResult], writable: bool = False
    ) -> dict[str, Any]:
        attempt_id = str(uuid.uuid4())
        attempt = {"id": attempt_id, "phase": phase, "started_at": now(), "status": "running"}
        state["agent_attempts"] = [*state.get("agent_attempts", []), attempt][-100:]
        await poll()
        try:
            result, usage = await agent.run(
                context_prompt(row["prd"], state, row.get("clarification", "")) + "\n\n" + prompt,
                contract,
                attempt_id,
                poll,
                remaining(),
                writable,
            )
            for key in ["input", "output"]:
                state["tokens"][key] += usage[key]
            attempt["status"] = "completed"
            return result
        except BaseException:
            attempt["status"] = "interrupted"
            raise
        finally:
            attempt["ended_at"] = now()

    try:
        await poll()
        work = Workspace(Path(row["repository_path"]), data_dir, str(row["id"]), lock_fd)
        agent = agent_factory(work, row.get("model", ""))
        # An interrupted attempt's local edits are intentional partial work. They are
        # checkpointed before continuing, never assumed to be a completed task.
        if phase != "prepare":
            await work.prepare()
            interrupted = [a for a in state.get("agent_attempts", []) if a["status"] == "running"]
            if interrupted:
                state["head_commit"] = await work.checkpoint("chore: recover interrupted attempt")
                for attempt in interrupted:
                    attempt["status"] = "interrupted"
                event(state, "Recovered interrupted attempt; task still requires verification")
        if phase == "prepare":
            state["base_commit"] = await work.prepare()
            state.update(
                {
                    "branch": work.branch,
                    "workspace_path": str(work.path),
                    "head_commit": await work.git("rev-parse", "HEAD"),
                    "phase": "plan",
                }
            )
            event(state, "Created isolated worktree; original checkout is unchanged")
        elif phase == "plan":
            status = "planning"
            state["plan"] = await ask(
                "You are the PLANNER only, not the implementer. Your read-only sandbox is "
                "intentional; a separate writable coding phase follows. This is not a blocker. "
                "Use clarification='' unless missing USER information or external access "
                "actually prevents planning. Inspect the repository and PRD. "
                "Produce a small dependency-ordered task plan. "
                "Every requirement needs concrete acceptance commands with meaningful assertions. "
                "Commands are argv arrays run from the repository root, without implicit shell. "
                "Include existing build/test checks and new behavioral checks. New tests may be "
                "implemented in a task. Avoid echo/true and mere file-presence checks. "
                "Use available runtimes; report missing requirements in clarification. "
                "Check argv escaping carefully: JSON decoding happens once; the resulting "
                "strings are passed directly to the executable, not through a shell. "
                "Do not edit repository files. IDs: R1, T1, C1 etc.",
                Plan,
            )
            plan = Plan.model_validate(state["plan"])
            state["phase"] = "plan_review"
            if plan.clarification:
                status, reason = "blocked", plan.clarification
                state["phase"] = "plan"
            event(state, "Created requirement-linked tasks and acceptance checks")
        elif phase == "plan_review":
            status = "planning"
            review = await ask(
                "Independently compare the plan against the full PRD. Check requirement coverage, "
                "task dependencies and whether acceptance commands assert observable behavior. "
                "Check actual argv syntax and string escaping after one JSON decode. "
                "Reject tautological/no-op verification and untestable claims. Read only. "
                "Return passed=true and findings=[] only if the plan can substantiate every "
                "requested behavior. Findings are blocking defects only, never positive "
                "observations or explanations of why the plan passed.",
                Review,
            )
            state["plan_review"] = review
            if review["passed"] and not review["findings"]:
                state["phase"] = "implement"
                state["plan_frozen_at"] = now()
                event(state, "Acceptance criteria frozen after independent plan review")
            else:
                state["failure_count"] = state.get("failure_count", 0) + 1
                state["review"] = review
                state["phase"] = "plan"
                if state["failure_count"] >= 3:
                    status, reason = (
                        "blocked",
                        "Plan review repeatedly failed: " + "; ".join(review["findings"]),
                    )
        elif phase == "implement":
            status = "executing"
            plan = Plan.model_validate(state["plan"])
            completed = set(state["completed_task_ids"])
            task = next(
                (t for t in plan.tasks if t.id not in completed and set(t.depends_on) <= completed),
                None,
            )
            if task is None:
                state["phase"] = "verify"
            else:
                if state["attempts"] >= int(row["max_attempts"]):
                    raise RunInterruptedError("exhausted")
                state["attempts"] += 1
                state["current_task_id"] = task.id
                before = await work.fingerprint()
                result = await ask(
                    "Implement this task and run relevant checks. Preserve the frozen acceptance "
                    "criteria. Do not remove or weaken tests to obtain passing results. "
                    "The supervisor handles commits, pushes, PRs and deployment.\n"
                    + task.model_dump_json(),
                    AgentResult,
                    writable=True,
                )
                state["head_commit"] = await work.checkpoint(f"feat: {task.title[:120]}")
                if result["blocked_reason"]:
                    status, reason = "blocked", result["blocked_reason"]
                else:
                    state["completed_task_ids"].append(task.id)
                    event(state, f"Task {task.id}: {result['summary']}")
                state["failure_count"] = (
                    0 if before != await work.fingerprint() else state.get("failure_count", 0) + 1
                )
                if state["failure_count"] >= 3:
                    status, reason = "blocked", "Three coding attempts made no repository progress"
                state["evidence"] = []
                state["review"] = {"passed": False, "findings": []}
        elif phase == "verify":
            status = "verifying"
            plan = Plan.model_validate(state["plan"])
            state["head_commit"] = await work.checkpoint(
                "chore: checkpoint before acceptance checks"
            )
            state["evidence"] = []
            for check in plan.checks:
                await poll()
                check_result = await agent.verify_command(
                    check.argv, str(uuid.uuid4()), poll, min(check.timeout_seconds, remaining())
                )
                state["evidence"].append(
                    {
                        "check_id": check.id,
                        "requirement_ids": check.requirement_ids,
                        "argv": check.argv,
                        "exit_code": check_result.exit_code,
                        "passed": check_result.exit_code == 0,
                        "commit": state["head_commit"],
                        "output": (check_result.stdout + check_result.stderr)[-12000:],
                        "at": now(),
                    }
                )
            # Check runners may create build artifacts, but must not alter tracked source.
            changed = await work.git("status", "--porcelain")
            if changed:
                status, reason = (
                    "blocked",
                    "Acceptance commands changed tracked or unignored files; review required",
                )
            elif all(e["passed"] for e in state["evidence"]):
                state["phase"] = "review"
                event(state, "All acceptance commands passed; independent review next")
            else:
                state["phase"] = "repair"
                failed = sorted(e["check_id"] for e in state["evidence"] if not e["passed"])
                state["repeated_failures"] = (
                    state.get("repeated_failures", 0) + 1
                    if failed == state.get("last_failed_checks")
                    else 1
                )
                state["last_failed_checks"] = failed
                if state["repeated_failures"] >= 3:
                    status, reason = (
                        "blocked",
                        "The same acceptance checks failed three times without improvement",
                    )
                event(state, "Acceptance checks failed; preparing targeted repair")
        elif phase == "review":
            status = "verifying"
            state["review"] = await ask(
                "Independently review the actual repository, PRD, frozen plan, diff and recorded "
                "acceptance evidence. Check every requirement and test validity, including whether "
                "tests were weakened, skipped or tautological. Read the actual code and tests. "
                "Do not edit files. Return passed=true with empty findings only if no material "
                "requirement gaps or correctness problems remain. Findings are blocking "
                "defects only, never positive observations or explanations of success.",
                Review,
            )
            state["phase"] = (
                "deliver"
                if state["review"]["passed"] and not state["review"]["findings"]
                else "repair"
            )
        elif phase == "repair":
            status = "executing"
            if state["attempts"] >= int(row["max_attempts"]):
                raise RunInterruptedError("exhausted")
            state["attempts"] += 1
            before = await work.fingerprint()
            result = await ask(
                "Repair failed acceptance checks and independent review findings in the context. "
                "Keep all frozen acceptance criteria intact. Fix the implementation and add "
                "regression coverage. Do not weaken or remove checks. Do not commit or publish.",
                AgentResult,
                writable=True,
            )
            state["head_commit"] = await work.checkpoint("fix: address acceptance findings")
            state["failure_count"] = (
                0 if before != await work.fingerprint() else state.get("failure_count", 0) + 1
            )
            if result["blocked_reason"]:
                status, reason = "blocked", result["blocked_reason"]
            elif state["failure_count"] >= 3:
                status, reason = "blocked", "Three repair attempts made no repository progress"
            else:
                state["phase"] = "verify"
            event(state, result["summary"])
        elif phase == "deliver":
            status, reason = await _deliver(row, state, work, poll, remaining)
        else:
            status, reason = "failed", f"Unknown execution phase: {phase}"
    except RunInterruptedError as exc:
        status = {"pause": "paused", "cancel": "canceled", "exhausted": "exhausted"}[exc.action]
        reason = (
            "Run limit reached; extend limits to resume"
            if status == "exhausted"
            else f"Run {status} by user"
        )
        consumed_action = exc.action
        event(state, reason)
    except Exception as exc:
        status, reason = "blocked", f"{type(exc).__name__}: {exc}"
        event(state, reason)
    finally:
        state["active_seconds"] = elapsed + time.monotonic() - start
        status = await store.save(state, status, reason)
        if consumed_action:
            await store.consume_control(consumed_action, control_version)
    return {"status": status, "reason": reason}


async def _deliver(
    row: dict[str, Any],
    state: dict[str, Any],
    work: Workspace,
    poll: Callable[[], Awaitable[None]],
    remaining: Callable[[], float],
) -> tuple[str, str]:
    plan = Plan.model_validate(state["plan"])
    head = await work.git("rev-parse", "HEAD")
    if await work.git("status", "--porcelain") or not completion_ready(
        plan,
        state["completed_task_ids"],
        state["evidence"],
        head,
        state.get("review", {}).get("passed", False)
        and not state.get("review", {}).get("findings"),
    ):
        return "blocked", "Completion evidence does not match the current repository revision"
    summary = f"# {row['name']}\n\n{plan.summary}\n\nBranch: {work.branch}\nCommit: {head}\n\n"
    summary += "\n".join(f"- [x] {r.id}: {r.description}" for r in plan.requirements)
    summary += "\n\n## Verification\n\n" + "\n".join(
        f"- {e['check_id']}: exit {e['exit_code']} at {e['commit']}" for e in state["evidence"]
    )
    state["summary"] = summary
    state["artifacts"] = [
        {"name": "verification.md", "media_type": "text/markdown", "content": summary},
        {
            "name": "changes.diff",
            "media_type": "text/plain",
            "content": (await work.diff(state["base_commit"]))[:500000],
        },
        {
            "name": "acceptance.json",
            "media_type": "application/json",
            "content": json.dumps(state["evidence"], indent=2),
        },
    ]
    if row.get("request_pr") and not state.get("pr_url"):
        # Publication is an explicit run option. A failed publish is resumable and
        # cannot disguise a missing requested deliverable as a completed run.
        result = await run_process(
            ["git", "push", "origin", f"HEAD:refs/heads/{work.branch}"],
            work.path,
            min(120, remaining()),
            poll,
            lock_fd=work.lock_fd,
        )
        if result.exit_code:
            return "blocked", "Branch verified; publication failed: " + result.stderr[-2000:]
        existing = await run_process(
            ["gh", "pr", "list", "--head", work.branch, "--json", "url"],
            work.path,
            60,
            poll,
            lock_fd=work.lock_fd,
        )
        if existing.exit_code:
            return "blocked", "Branch pushed; could not check existing PR: " + existing.stderr[
                -2000:
            ]
        urls = json.loads(existing.stdout)
        if urls:
            state["pr_url"] = urls[0]["url"]
        else:
            body = work.root / "pr-body.md"
            body.write_text(summary)
            created = await run_process(
                [
                    "gh",
                    "pr",
                    "create",
                    "--head",
                    work.branch,
                    "--title",
                    row["name"],
                    "--body-file",
                    str(body),
                ],
                work.path,
                120,
                poll,
                lock_fd=work.lock_fd,
            )
            if created.exit_code:
                return "blocked", "Branch pushed; PR creation failed: " + created.stderr[-2000:]
            state["pr_url"] = created.stdout.strip()
    event(state, "Delivered verified branch and acceptance evidence")
    return "completed", ""
