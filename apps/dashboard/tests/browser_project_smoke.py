"""Browser contract checks for project intake, run controls, evidence, and replay.

Run against a dashboard dev server; RPC responses are deliberately mocked:
    python3 tests/browser_project_smoke.py --url http://localhost:3100

Requires Python Playwright and its Chromium browser. This does not substitute
for the repository's real API/runner integration checks.
"""

import argparse
import json

from playwright.sync_api import expect, sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:3100")
    parser.add_argument("--screenshot", default="/tmp/harnessflow-project-run.png")
    args = parser.parse_args()
    project = {
        "id": "project-1", "name": "Feedback portal",
        "repositoryPath": "/tmp/feedback-portal", "prd": "Build a feedback portal.",
        "createdAt": "2026-10-10T12:00:00Z",
    }
    snapshot = {
        "phase": "judge", "branch": "harnessflow/run-1",
        "workspace_path": "/tmp/harnessflow/run-1", "head_commit": "abc123def456",
        "attempts": 2, "active_seconds": 180,
        "tokens": {"input": 1500, "output": 500},
        "plan": {
            "summary": "Deliver a small feedback portal with persisted entries.",
            "requirements": [{"id": "R1", "description": "Users can save feedback."}],
            "tasks": [{"id": "T1", "title": "Implement feedback form", "requirement_ids": ["R1"], "instructions": "Add form and persistence."}],
            "checks": [{"id": "C1", "description": "Submission persists", "requirement_ids": ["R1"], "argv": ["npm", "test"]}],
        },
        "completed_task_ids": [],
        "events": [{"at": "2026-10-10T12:03:00Z", "message": "Implementing feedback form"}],
        "evidence": [{"check_id": "C1", "requirement_ids": ["R1"], "argv": ["npm", "test"], "exit_code": 0, "output": "1 test passed", "commit": "abc123def456", "passed": True}],
        "judge": {
            "passed": True, "provider": "openai", "model": "gpt-5",
            "commit": "abc123def456", "findings": [],
            "requirement_verdicts": [{"requirement_id": "R1", "passed": True, "reason": "Feedback submissions persist after reload."}],
        },
        "artifacts": [{"name": "changes.diff", "content": "+ export function FeedbackForm() {}", "media_type": "text/plain"}],
    }
    run = {"id": "run-1", "projectId": "project-1", "status": "running", "snapshotJson": json.dumps(snapshot), "createdAt": "2026-10-10T12:00:00Z"}
    calls = []
    created = False
    pending_status = None
    pending_polls = 0

    def rpc(route):
        nonlocal created, pending_status, pending_polls
        request = route.request
        headers = {"access-control-allow-origin": "*", "access-control-allow-headers": "*", "access-control-allow-methods": "POST, OPTIONS"}
        if request.method == "OPTIONS":
            route.fulfill(status=204, headers=headers)
            return
        method = request.url.rsplit("/", 1)[-1]
        body = request.post_data_json or {}
        calls.append((method, body))
        if "harnessflow.project.v1" in request.url:
            if method == "ListProjects": response = {"projects": [project] if created else []}
            elif method == "CreateProject":
                project.update(body)
                created = True
                response = {"project": project}
            elif method == "GetProject": response = {"project": project}
            elif method == "ListRuns": response = {"runs": []}
            elif method in ("StartRun", "GetRun"):
                if method == "GetRun" and pending_status:
                    pending_polls += 1
                    if pending_polls >= 2:
                        run["status"] = pending_status
                        run["reason"] = "Paused at checkpoint." if pending_status == "paused" else ""
                        pending_status = None
                response = {"run": run}
            elif method == "ControlRun":
                action = body["action"]
                pending_status = {"pause": "paused", "resume": "running", "cancel": "canceled"}[action]
                pending_polls = 0
                response = {"run": run}
            elif method == "GetArtifacts": response = {"snapshotJson": run["snapshotJson"]}
            else: raise AssertionError(f"Unexpected RPC {method}")
        elif "harnessflow.run.v1" in request.url:
            response = {"run": {"id": "legacy-1", "workflowId": "workflow-1", "status": "RUN_STATUS_COMPLETED", "startedAt": "2026-10-10T12:00:00Z", "endedAt": "2026-10-10T12:00:04Z"}, "steps": [{"id": "step-1", "name": "executor", "type": "llm_call", "status": "STEP_STATUS_COMPLETED", "startedAt": "2026-10-10T12:00:00Z", "endedAt": "2026-10-10T12:00:04Z", "outputPreview": "A useful answer"}]}
        else:
            raise AssertionError(f"Unexpected RPC {request.url}")
        route.fulfill(status=200, content_type="application/json", headers=headers, body=json.dumps(response))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.route("**/harnessflow.*/**", rpc)
        page.goto(args.url)
        page.wait_for_load_state("networkidle")
        expect(page.get_by_role("heading", name="Give your project a clear next step.")).to_be_visible()
        page.screenshot(path="/tmp/harnessflow-project-intake.png", full_page=True)
        page.get_by_label("Project name", exact=True).fill("Feedback portal")
        page.get_by_label("Local repository path", exact=False).fill("/tmp/feedback-portal")
        page.get_by_label("Import Markdown or text").set_input_files({"name": "brief.md", "mimeType": "text/markdown", "buffer": b"Build a feedback portal with acceptance tests."})
        expect(page.get_by_label("Product brief / PRD")).to_have_value("Build a feedback portal with acceptance tests.")
        page.get_by_role("button", name="Create project").click()
        page.wait_for_url("**/projects/project-1")
        expect(page.get_by_role("heading", name="Feedback portal")).to_be_visible()
        expect(page.get_by_label("Coding attempts", exact=False)).to_have_value("30")
        expect(page.get_by_label("Active time limit (minutes)", exact=False)).to_have_value("240")
        page.get_by_role("button", name="Start building").click()
        page.wait_for_url("**/projects/project-1/runs/run-1")
        expect(page.get_by_role("heading", name="Implement feedback form")).to_be_visible()
        expect(page.get_by_text("Users can save feedback.")).to_be_visible()
        phases = page.get_by_label("Run phases")
        expect(phases.locator("span").nth(5)).to_contain_text("review")
        expect(phases.locator("span").nth(6)).to_contain_text("judge")
        expect(page.get_by_text("Judge evidence")).to_be_visible()
        expect(page.get_by_text("openai · gpt-5")).to_be_visible()
        expect(page.get_by_text("Feedback submissions persist after reload.")).to_be_visible()
        expect(page.locator("p").filter(has_text="Commit abc123def456").last).to_be_visible()
        page.locator("summary").filter(has_text="C1").click()
        expect(page.get_by_text("1 test passed", exact=False)).to_be_visible()
        page.locator("summary").filter(has_text="changes.diff").click()
        expect(page.get_by_text("+ export function FeedbackForm() {}", exact=True)).to_be_visible()
        page.get_by_role("button", name="Pause run", exact=True).click()
        expect(page.get_by_text("Pause request saved.", exact=False)).to_be_visible()
        expect(page.get_by_role("button", name="Pause run", exact=True)).to_be_disabled()
        expect(page.get_by_role("button", name="Resume run", exact=True)).to_be_visible()
        page.get_by_label("Clarification or additional context").fill("Use SQLite for persistence.")
        page.get_by_label("Additional coding attempts").fill("3")
        page.get_by_label("Additional active minutes").fill("30")
        page.get_by_role("button", name="Resume run", exact=True).click()
        expect(page.get_by_role("button", name="Resume run", exact=True)).to_be_disabled()
        expect(page.get_by_role("button", name="Pause run", exact=True)).to_be_visible()
        resume = [body for method, body in calls if method == "ControlRun" and body["action"] == "resume"][-1]
        assert resume["clarification"] == "Use SQLite for persistence."
        assert resume["additionalAttempts"] == 3 and resume["additionalSeconds"] == 1800
        started = [body for method, body in calls if method == "StartRun"][-1]
        assert started["maxAttempts"] == 30 and started["maxDurationSeconds"] == 14400
        page.evaluate("window.scrollTo(0, 0)")
        page.screenshot(path=args.screenshot, full_page=True)
        page.get_by_role("button", name="Cancel run", exact=True).click()
        expect(page.get_by_role("button", name="Confirm cancel")).to_be_visible()
        page.get_by_role("button", name="Confirm cancel").click()
        expect(page.get_by_text("canceled", exact=True)).to_be_visible()
        expect(page.get_by_role("heading", name="Run controls")).to_have_count(0)
        for status in ("blocked", "exhausted"):
            run["status"] = status
            run["reason"] = "More context or resources are needed."
            page.reload()
            expect(page.get_by_role("button", name="Resume run", exact=True)).to_be_visible()
            page.get_by_role("button", name="Resume run", exact=True).click()
            expect(page.get_by_role("button", name="Pause run", exact=True)).to_be_visible()
        run["status"] = "completed"
        snapshot["completed_task_ids"] = ["T1"]
        snapshot["summary"] = "Feedback portal is ready for review."
        snapshot["pr_url"] = "https://github.com/example/feedback/pull/1"
        run["snapshotJson"] = json.dumps(snapshot)
        page.reload()
        expect(page.get_by_role("heading", name="Delivery", exact=True)).to_be_visible()
        expect(page.get_by_role("link", name="Review pull request")).to_have_attribute("href", snapshot["pr_url"])
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Mobile layout overflows"
        page.goto(args.url + "/runs/legacy-1/replay")
        expect(page.get_by_role("heading", name="Run replay")).to_be_visible()
        expect(page.get_by_role("button", name="Replay", exact=False)).to_be_visible()
        page.get_by_role("button", name="Replay", exact=False).click()
        page.wait_for_function("Number(document.querySelector('input[type=range]').value) > 10 && Number(document.querySelector('input[type=range]').value) < 100")
        page.get_by_role("button", name="Pause", exact=True).click()
        cursor = page.get_by_role("slider").input_value()
        page.wait_for_timeout(200)
        assert page.get_by_role("slider").input_value() == cursor, "Replay pause must stop the cursor"
        assert not errors, errors
        browser.close()
    print("PASS: PRD import/create → run defaults → evidence/artifacts → pause/clarify/extend/resume → cancel → responsive layout → replay/pause")


if __name__ == "__main__":
    main()
