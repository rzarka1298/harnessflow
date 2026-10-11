"""The project judge uses an independent provider when available."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from harnessflow_worker.projects import judge as module

PLAN = {
    "summary": "Greeting",
    "assumptions": [],
    "requirements": [{"id": "R1", "description": "Greet"}],
    "tasks": [
        {
            "id": "T1",
            "title": "Greet",
            "instructions": "Greet",
            "requirement_ids": ["R1"],
            "depends_on": [],
        }
    ],
    "checks": [
        {
            "id": "C1",
            "description": "Check",
            "requirement_ids": ["R1"],
            "argv": ["python3", "-m", "unittest"],
            "timeout_seconds": 60,
        }
    ],
    "clarification": "",
}
VERDICT = {
    "passed": True,
    "findings": [],
    "requirement_verdicts": [{"requirement_id": "R1", "passed": True, "reason": "Tested"}],
}


class Workspace:
    async def git(self, *args):
        assert args == ("rev-parse", "HEAD")
        return "abc"

    async def diff(self, base):
        assert base == "base"
        return "+greeting"


class Agent:
    model = ""

    async def run(self, prompt, contract, name, poll, timeout, writable=False):
        assert contract is module.JudgeVerdict
        assert not writable
        assert "independent acceptance judge" in prompt
        return VERDICT, {"input": 2, "output": 1}


async def poll():
    pass


def state():
    return {
        "plan": PLAN,
        "base_commit": "base",
        "evidence": [],
        "review": {"passed": True, "findings": []},
    }


@pytest.mark.asyncio
async def test_codex_fallback_is_explicit_read_only_attempt(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result, usage = await module.judge_project(
        workspace=Workspace(),
        agent=Agent(),
        prd="Greet",
        state=state(),
        clarification="",
        poll=poll,
        timeout=30,
        attempt_id="attempt",
    )
    assert result == {**VERDICT, "provider": "codex", "model": "default", "commit": "abc"}
    assert usage == {"input": 2, "output": 1}


@pytest.mark.asyncio
async def test_anthropic_judge_receives_diff_and_evidence(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    seen = {}

    class Provider:
        def __init__(self, client):
            pass

        async def complete(self, model, prompt, **kwargs):
            seen.update(model=model, prompt=prompt, kwargs=kwargs)
            return SimpleNamespace(text=json.dumps(VERDICT), input_tokens=3, output_tokens=2)

    monkeypatch.setattr(module, "AnthropicProvider", Provider)
    result, usage = await module.judge_project(
        workspace=Workspace(),
        agent=Agent(),
        prd="Greet",
        state=state(),
        clarification="",
        poll=poll,
        timeout=30,
        attempt_id="attempt",
    )
    assert seen["model"] == "claude-sonnet-4-6"
    assert "+greeting" in seen["prompt"]
    assert "R1" in seen["prompt"]
    assert result["provider"] == "anthropic"
    assert result["commit"] == "abc"
    assert usage == {"input": 3, "output": 2}
