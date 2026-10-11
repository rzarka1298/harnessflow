"""Small standard-library client for HarnessFlow's Connect JSON API."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_API = "http://127.0.0.1:8080"
DEFAULT_DASHBOARD = "http://127.0.0.1:3001"
SERVICE = "/harnessflow.project.v1.ProjectService/"
STOPPED = {"completed", "failed", "canceled", "paused", "blocked", "exhausted"}


class CLIError(Exception):
    """An actionable input, API, or network error."""


def _api_call(api: str, method: str, payload: dict) -> dict:
    url = api.rstrip("/") + SERVICE + method
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Connect-Protocol-Version": "1"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            detail = {}
        message = detail.get("message") or detail.get("error") or str(exc.reason)
        code = detail.get("code")
        raise CLIError(f"API {method} failed ({code or exc.code}): {message}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise CLIError(f"Could not reach HarnessFlow API at {api}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise CLIError(f"API {method} returned invalid JSON") from exc
    if not isinstance(result, dict):
        raise CLIError(f"API {method} returned an unexpected response")
    return result


def _git_root(repo: Path) -> Path:
    try:
        result = subprocess.run(
            ["git", "-C", os.fspath(repo), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (
        FileNotFoundError,
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
    ) as exc:
        raise CLIError(f"Repository must be inside a local Git repository: {repo}") from exc
    return Path(result.stdout.strip()).resolve(strict=True)


def _inside(path: Path, roots: tuple[Path, ...]) -> bool:
    return any(path == root or root in path.parents for root in roots)


def _resolve_prd(raw_path: str, repo_root: Path) -> Path:
    supplied = Path(raw_path).expanduser()
    if supplied.is_absolute():
        candidates = [supplied]
    else:
        cwd = Path.cwd().resolve()
        candidates = [cwd / supplied]
        repository_candidate = repo_root / supplied
        if repository_candidate != candidates[0]:
            candidates.append(repository_candidate)
    for candidate in candidates:
        try:
            resolved = candidate.resolve(strict=True)
        except OSError:
            continue
        if not resolved.is_file():
            raise CLIError(f"PRD path is not a file: {resolved}")
        if not supplied.is_absolute() and not _inside(resolved, (Path.cwd().resolve(), repo_root)):
            raise CLIError(
                "Relative PRD paths must stay inside the current directory or repository"
            )
        return resolved
    raise CLIError(f"PRD file not found: {raw_path}")


def _emit(value: dict) -> None:
    print(json.dumps(value, ensure_ascii=False, separators=(",", ":")))


def _dashboard_url(dashboard: str, project_id: str, run_id: str) -> str:
    return f"{dashboard.rstrip('/')}/projects/{project_id}/runs/{run_id}"


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _run(args: argparse.Namespace) -> int:
    repo_root = _git_root(Path(args.repo or Path.cwd()).expanduser().resolve())
    prd_path = _resolve_prd(args.prd, repo_root)
    try:
        prd = prd_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise CLIError(f"Could not read UTF-8 PRD at {prd_path}: {exc}") from exc
    project_response = _api_call(
        args.api,
        "CreateProject",
        {
            "name": args.name or prd_path.stem,
            "repositoryPath": str(repo_root),
            "prd": prd,
        },
    )
    project = project_response.get("project")
    if not isinstance(project, dict) or not project.get("id"):
        raise CLIError("API CreateProject response did not contain a project ID")
    run_request = {"projectId": project["id"]}
    if args.max_attempts is not None:
        run_request["maxAttempts"] = args.max_attempts
    if args.max_duration_seconds is not None:
        run_request["maxDurationSeconds"] = args.max_duration_seconds
    if args.model:
        run_request["model"] = args.model
    if args.request_pr:
        run_request["requestPr"] = True
    run_response = _api_call(args.api, "StartRun", run_request)
    run = run_response.get("run")
    if not isinstance(run, dict) or not run.get("id"):
        raise CLIError("API StartRun response did not contain a run ID")
    result = {
        "project_id": project["id"],
        "run_id": run["id"],
        "status": run.get("status", "queued"),
        "dashboard_url": _dashboard_url(args.dashboard, project["id"], run["id"]),
    }
    _emit(result)
    if args.wait:
        while result["status"] not in STOPPED:
            time.sleep(2)
            response = _api_call(args.api, "GetRun", {"id": run["id"]})
            current = response.get("run")
            if not isinstance(current, dict):
                raise CLIError("API GetRun response did not contain a run")
            result["status"] = current.get("status", "unknown")
            _emit(result)
        return 0 if result["status"] == "completed" else 1
    return 0


def _control(args: argparse.Namespace, action: str) -> int:
    payload = {"runId": args.run_id, "action": action}
    if action == "resume":
        if args.clarification:
            payload["clarification"] = args.clarification
        if args.max_attempts is not None:
            payload["additionalAttempts"] = args.max_attempts
        if args.max_duration_seconds is not None:
            payload["additionalSeconds"] = args.max_duration_seconds
    response = _api_call(args.api, "ControlRun", payload)
    run = response.get("run")
    if not isinstance(run, dict) or not run.get("id"):
        raise CLIError(f"API {action} response did not contain a run")
    output = {"run_id": run["id"], "status": run.get("status"), "action": action}
    if run.get("projectId"):
        output["dashboard_url"] = _dashboard_url(args.dashboard, run["projectId"], run["id"])
    _emit(output)
    return 0


def _status(args: argparse.Namespace) -> int:
    response = _api_call(args.api, "GetRun", {"id": args.run_id})
    run = response.get("run")
    if not isinstance(run, dict) or not run.get("id"):
        raise CLIError("API GetRun response did not contain a run")
    if args.full:
        _emit(run)
        return 0
    summary = {
        "run_id": run["id"],
        "project_id": run.get("projectId"),
        "status": run.get("status"),
        "reason": run.get("reason", ""),
    }
    if run.get("projectId"):
        summary["dashboard_url"] = _dashboard_url(args.dashboard, run["projectId"], run["id"])
    try:
        snapshot = json.loads(run.get("snapshotJson") or "{}")
    except json.JSONDecodeError:
        summary["snapshot_error"] = "Run snapshot is invalid JSON"
    else:
        if isinstance(snapshot, dict):
            summary["phase"] = snapshot.get("phase")
            summary["branch"] = snapshot.get("branch")
            summary["commit"] = snapshot.get("head_commit")
            judge = snapshot.get("judge")
            if isinstance(judge, dict):
                summary["judge"] = {
                    key: judge.get(key) for key in ("passed", "provider", "model", "commit")
                }
    _emit(summary)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="harnessflow", description="Run local PRDs with HarnessFlow"
    )
    parser.add_argument("--api", default=DEFAULT_API, help=f"API base URL (default: {DEFAULT_API})")
    parser.add_argument(
        "--dashboard",
        default=DEFAULT_DASHBOARD,
        help=f"dashboard base URL (default: {DEFAULT_DASHBOARD})",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="create a project and start a run from a PRD")
    run.add_argument(
        "prd", help="PRD file, absolute or relative to the current directory/repository"
    )
    run.add_argument("--repo", help="Git repository path; defaults to the current directory")
    run.add_argument("--name", help="project name (defaults to PRD filename)")
    run.add_argument("--max-attempts", type=_positive_int, help="coding attempt limit")
    run.add_argument("--max-duration-seconds", type=_positive_int, help="active time limit")
    run.add_argument("--model", help="Codex model override")
    run.add_argument(
        "--request-pr", action="store_true", help="publish a GitHub PR after verification"
    )
    run.add_argument(
        "--wait",
        action="store_true",
        help="poll until the run reaches a terminal state",
    )
    run.add_argument("--api", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    run.add_argument("--dashboard", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    run.set_defaults(handler=_run)
    status = commands.add_parser("status", help="show a run's current state")
    status.add_argument("run_id")
    status.add_argument(
        "--full", action="store_true", help="print the complete API run and snapshot"
    )
    status.add_argument("--api", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    status.add_argument("--dashboard", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    status.set_defaults(handler=_status)
    for action in ("resume", "pause", "cancel"):
        command = commands.add_parser(action, help=f"{action} a run")
        command.add_argument("run_id")
        command.add_argument("--api", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
        command.add_argument("--dashboard", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
        if action == "resume":
            command.add_argument("--clarification")
            command.add_argument(
                "--max-attempts", type=int, help="additional repair attempts to allow"
            )
            command.add_argument(
                "--max-duration-seconds",
                type=int,
                help="additional run seconds to allow",
            )
        command.set_defaults(handler=_control, action=action)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        code = (
            args.handler(args)
            if args.command not in {"resume", "pause", "cancel"}
            else _control(args, args.action)
        )
    except CLIError as exc:
        print(f"harnessflow: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    raise SystemExit(code)


if __name__ == "__main__":
    main()
