#!/usr/bin/env python3
"""CI eval-gate helper.

Given one or more changed ``packages/examples/workflows/*.yaml`` files, this:

  1. Reads the **baseline** version of each file from a git ref (default
     ``origin/main``) and the **PR** version from the working tree.
  2. Registers both via ``WorkflowService.CreateWorkflow`` on a running API.
  3. Runs the eval suite against each (baseline first, then PR) using the
     ``harnessflow-eval`` CLI, with the PR run gated against the baseline.
  4. Concatenates the per-file markdown into a single comment body and writes
     it to ``--out-md``.
  5. Exits nonzero if any file's gate failed.

Why a separate helper instead of inlining in the workflow YAML: bash + YAML
loops + JSON munging get illegible fast, and we want the gate logic
testable locally against the dev stack — see the ``--changed-files`` flag.

Assumptions:
  - The HarnessFlow stack (postgres + temporal + api + worker) is running
    and reachable at ``--api-base-url``.
  - The workflow basename (e.g. ``research-assistant``) maps 1:1 to a
    dataset of the same name under ``apps/eval-runner/harnessflow_eval/datasets/``.
    Files without a matching dataset (e.g. ``approval-demo.yaml``) are
    skipped with a logged note.
  - The eval-runner CLI is invocable as ``uv run --directory apps/eval-runner
    harnessflow-eval`` from the repo root.

The CI workflow (``.github/workflows/eval-gate.yml``) is the canonical
caller; this script is intentionally invocable by hand for local testing.
"""

from __future__ import annotations

import argparse
import re
import shlex
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
DATASETS_DIR = REPO_ROOT / "apps" / "eval-runner" / "harnessflow_eval" / "datasets"

CREATE_WORKFLOW = "/harnessflow.workflow.v1.WorkflowService/CreateWorkflow"


def _log(msg: str) -> None:
    # Plain prints; GHA renders them inline in the job log without extra prefixing.
    print(f"[ci-eval-gate] {msg}", flush=True)


def _git_show(ref: str, path: str) -> str | None:
    """Return the contents of ``path`` at ``ref``, or None if the file
    doesn't exist on that ref (e.g. a workflow newly added in the PR)."""
    try:
        out = subprocess.run(
            ["git", "show", f"{ref}:{path}"],
            check=True,
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
    except subprocess.CalledProcessError:
        return None
    return out.stdout


# The workflows table has a UNIQUE (name, version) constraint, so registering
# the same YAML twice for the same name/version collides. The CI gate
# registers a baseline+PR pair per file (and may run multiple times per
# session), so we mangle the ``name:`` field with a short unique suffix
# before posting. The mangled name is only used as a DB row label; the eval
# runner targets workflows by id.
_NAME_RE = re.compile(r"^(name:\s*)([^\n]+)$", re.MULTILINE)


def _mangle_name(yaml_src: str, role: str) -> str:
    suffix = uuid.uuid4().hex[:8]
    return _NAME_RE.sub(rf"\g<1>\g<2>-gate-{role}-{suffix}", yaml_src, count=1)


def _create_workflow(client: httpx.Client, base_url: str, yaml_src: str) -> str:
    r = client.post(
        f"{base_url}{CREATE_WORKFLOW}",
        headers={"Content-Type": "application/json"},
        json={"yaml_source": yaml_src},
    )
    r.raise_for_status()
    wid = r.json()["workflow"]["id"]
    return str(wid)


def _run_eval(
    *,
    workflow_id: str,
    dataset: str,
    api_base_url: str,
    out_json: Path,
    out_md: Path,
    baseline_json: Path | None,
    gate_max_regression: float | None,
) -> int:
    """Invoke the eval-runner CLI; return its exit code."""
    cmd = [
        "uv",
        "run",
        "--directory",
        str(REPO_ROOT / "apps" / "eval-runner"),
        "harnessflow-eval",
        "--workflow-id",
        workflow_id,
        "--dataset",
        dataset,
        "--api-base-url",
        api_base_url,
        "--out-json",
        str(out_json),
        "--out-md",
        str(out_md),
    ]
    if baseline_json is not None:
        cmd += ["--baseline-json", str(baseline_json)]
    if gate_max_regression is not None:
        cmd += ["--gate-max-regression", str(gate_max_regression)]
    _log(f"$ {shlex.join(cmd)}")
    return subprocess.call(cmd, cwd=REPO_ROOT)


def _wait_for_api(base_url: str, timeout_s: float = 60.0) -> None:
    """Poll /readyz until 200, so a fresh stack has time to settle."""
    deadline = time.time() + timeout_s
    last_err = ""
    while time.time() < deadline:
        try:
            r = httpx.get(f"{base_url}/readyz", timeout=2.0)
            if r.status_code == 200:
                _log(f"api ready at {base_url}")
                return
            last_err = f"http {r.status_code}"
        except httpx.HTTPError as exc:
            last_err = str(exc)
        time.sleep(1.0)
    raise SystemExit(f"api at {base_url} never became ready ({last_err})")


def _dataset_for(workflow_path: Path) -> str | None:
    """Pick the dataset to score a workflow YAML against. Convention: the
    workflow stem matches the dataset filename (e.g. ``research-assistant.yaml``
    → ``datasets/research-assistant.jsonl``). Returns None when no matching
    dataset exists — those files are skipped (we log it)."""
    stem = workflow_path.stem
    if (DATASETS_DIR / f"{stem}.jsonl").exists():
        return stem
    return None


def main() -> int:
    p = argparse.ArgumentParser(prog="ci-eval-gate")
    p.add_argument(
        "--changed-files",
        nargs="+",
        required=True,
        help="Paths (relative to repo root) of workflow YAMLs changed in the PR.",
    )
    p.add_argument(
        "--baseline-ref",
        default="origin/main",
        help="Git ref to treat as the baseline (default: origin/main).",
    )
    p.add_argument(
        "--api-base-url",
        default="http://localhost:8080",
    )
    p.add_argument(
        "--gate-max-regression",
        type=float,
        default=0.05,
        help="Allowed downward drop per scorer (default: 0.05). 0.0 = no drop allowed.",
    )
    p.add_argument(
        "--out-md",
        type=Path,
        required=True,
        help="Where to write the combined markdown comment body.",
    )
    p.add_argument(
        "--scratch-dir",
        type=Path,
        default=Path("/tmp/harnessflow-eval-gate"),
        help="Where to drop per-file baseline/current report artifacts.",
    )
    args = p.parse_args()

    args.scratch_dir.mkdir(parents=True, exist_ok=True)
    _wait_for_api(args.api_base_url)

    # Build the comment piece by piece. Worst exit code wins.
    comment_chunks: list[str] = ["## HarnessFlow eval-gate", ""]
    worst_exit = 0
    any_evaluated = False

    with httpx.Client(timeout=30.0) as client:
        for raw in args.changed_files:
            wf_path = Path(raw)
            label = wf_path.as_posix()
            _log(f"--- {label} ---")
            comment_chunks.append(f"### `{label}`")

            dataset = _dataset_for(wf_path)
            if dataset is None:
                msg = (
                    f"_Skipped — no dataset matches `{wf_path.stem}` under "
                    f"`apps/eval-runner/harnessflow_eval/datasets/`._"
                )
                _log(msg)
                comment_chunks += [msg, ""]
                continue

            pr_yaml_path = REPO_ROOT / wf_path
            if not pr_yaml_path.exists():
                msg = f"_Skipped — `{label}` was deleted in the PR; nothing to evaluate._"
                _log(msg)
                comment_chunks += [msg, ""]
                continue
            pr_yaml = pr_yaml_path.read_text()
            base_yaml = _git_show(args.baseline_ref, str(wf_path))

            safe_stem = wf_path.stem.replace("/", "_")
            base_json = args.scratch_dir / f"{safe_stem}.base.json"
            base_md = args.scratch_dir / f"{safe_stem}.base.md"
            pr_json = args.scratch_dir / f"{safe_stem}.pr.json"
            pr_md = args.scratch_dir / f"{safe_stem}.pr.md"

            if base_yaml is None:
                msg = (
                    f"_New workflow — no baseline on `{args.baseline_ref}`. "
                    f"Running PR eval ungated for visibility._"
                )
                _log(msg)
                comment_chunks += [msg, ""]
                pr_wf_id = _create_workflow(
                    client, args.api_base_url, _mangle_name(pr_yaml, "pr")
                )
                rc = _run_eval(
                    workflow_id=pr_wf_id,
                    dataset=dataset,
                    api_base_url=args.api_base_url,
                    out_json=pr_json,
                    out_md=pr_md,
                    baseline_json=None,
                    gate_max_regression=None,
                )
                if rc != 0:
                    _log(f"eval-runner exit {rc} on PR-only run for {label}")
                    worst_exit = max(worst_exit, rc)
                comment_chunks += [pr_md.read_text(), ""]
                any_evaluated = True
                continue

            # 1) baseline run
            base_wf_id = _create_workflow(
                client, args.api_base_url, _mangle_name(base_yaml, "base")
            )
            rc = _run_eval(
                workflow_id=base_wf_id,
                dataset=dataset,
                api_base_url=args.api_base_url,
                out_json=base_json,
                out_md=base_md,
                baseline_json=None,
                gate_max_regression=None,
            )
            if rc != 0:
                # Baseline crashing shouldn't fail the PR — but surface it.
                _log(f"eval-runner exit {rc} on baseline run for {label}")

            # 2) PR run, gated against baseline
            pr_wf_id = _create_workflow(
                client, args.api_base_url, _mangle_name(pr_yaml, "pr")
            )
            rc = _run_eval(
                workflow_id=pr_wf_id,
                dataset=dataset,
                api_base_url=args.api_base_url,
                out_json=pr_json,
                out_md=pr_md,
                baseline_json=base_json,
                gate_max_regression=args.gate_max_regression,
            )
            if rc != 0:
                worst_exit = max(worst_exit, rc)
            comment_chunks += [pr_md.read_text(), ""]
            any_evaluated = True

    if not any_evaluated:
        comment_chunks.append(
            "_No workflow files had a matching dataset; nothing to evaluate._"
        )

    args.out_md.write_text("\n".join(comment_chunks))
    _log(f"wrote comment body to {args.out_md} ({len(comment_chunks)} chunks)")
    _log(f"exit {worst_exit}")
    return worst_exit


if __name__ == "__main__":
    sys.exit(main())
