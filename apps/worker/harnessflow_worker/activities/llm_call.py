"""``llm_call`` activity — invokes the LLMClient with the step's model + prompt.

Step fields used (see packages/workflow-dsl/SPEC.md):
- model            (required)
- prompt           (required)
- fallback_on_rate_limit, fallback_on_5xx (optional)
- max_tokens, temperature                  (optional)
"""

from __future__ import annotations

from temporalio import activity

from harnessflow_worker.activities._common import ActivityFn, Deps, with_persistence
from harnessflow_worker.llm import LLMRequest
from harnessflow_worker.llm.pricing import provider_for
from harnessflow_worker.metrics import record_llm
from harnessflow_worker.types import ActivityInput, ActivityResult


def make_llm_call(deps: Deps) -> ActivityFn:
    @activity.defn(name="llm_call")
    async def llm_call(in_: ActivityInput) -> ActivityResult:
        async def body() -> ActivityResult:
            step = in_.step
            if not step.model or not step.prompt:
                raise ValueError("llm_call: 'model' and 'prompt' are required")
            prompt = _render_prompt(step.prompt, in_.run_inputs, in_.prior_outputs)
            rsp = await deps.llm.complete(
                LLMRequest(
                    model=step.model,
                    prompt=prompt,
                    max_tokens=step.max_tokens,
                    temperature=step.temperature,
                    fallback_on_rate_limit=step.fallback_on_rate_limit,
                    fallback_on_5xx=step.fallback_on_5xx,
                )
            )
            record_llm(
                in_.workflow_name,
                provider_for(rsp.model_used) or "unknown",
                rsp.model_used,
                rsp.input_tokens,
                rsp.output_tokens,
                rsp.cost_usd_cents,
            )
            return ActivityResult(
                output=rsp.text,
                input_tokens=rsp.input_tokens,
                output_tokens=rsp.output_tokens,
                cost_usd_cents=rsp.cost_usd_cents,
            )

        return await with_persistence(deps, in_, body)

    return llm_call


def _render_prompt(
    template: str,
    run_inputs: dict[str, str],
    prior_outputs: dict[str, ActivityResult],
) -> str:
    """Trivial mustache-flavored substitution.

    {{inputs.NAME}} -> run_inputs[NAME]
    {{steps.NAME.output}} -> prior_outputs[NAME].output

    Intentionally simple; a real templater (Jinja-style) lands when workflows
    routinely need control flow inside prompts.
    """
    out = template
    for k, v in run_inputs.items():
        out = out.replace("{{inputs." + k + "}}", v)
    for name, result in prior_outputs.items():
        out = out.replace("{{steps." + name + ".output}}", result.output)
    return out
