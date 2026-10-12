# ADR-0011: Isolate credentials before hosted real-model acceptance

Status: Accepted (2026-10-12)

## Context

HarnessFlow's local project worker launches Codex repeatedly and runs generated
code in acceptance checks. A proposed opt-in GitHub Actions job would need a
model credential for those nested invocations. Passing an OpenAI API key through
the job or worker environment would make it available to repository-controlled
commands and potentially to agent tool commands. The repository currently has
no protected GitHub environment or model secret. The existing real-Codex
acceptance runs were local and their commit-bound results are recorded separately.

The [official OpenAI non-interactive guidance](https://learn.chatgpt.com/docs/non-interactive-mode)
advises against job-level API keys in workflows that execute repository code and
recommends the [Codex GitHub Action](https://learn.chatgpt.com/docs/github-action)
for individual Codex invocations. That action's documented contract runs one
`codex exec`; using it as authentication for this worker's later nested Codex
subprocesses would be an unsupported assumption.

## Decision

Do not enable a hosted, key-bearing real-model acceptance workflow yet. First,
routine Git, publication and deterministic-check subprocesses must receive no
model credential; only the supervised Codex model-invocation path may receive one. This
change narrows accidental exposure but is not a complete hosted boundary,
because Codex and code it executes may still access its own process credentials.

Before hosted live acceptance is enabled, isolate the credential in a trusted
proxy or equivalent separate identity that the worker, fixture repository and
agent tool subprocesses cannot inspect. Then use a manually dispatched workflow
restricted to trusted `main`, a protected environment, fixed fixture inputs,
read-only repository permissions, bounded attempts and duration, no publication,
and a scoped model credential. Verify the boundary with tests that try to read
the secret from agent/tool and frozen-check processes. Provisioning and an
actual credentialed GitHub run remain separate work.

## Consequences

Ordinary CI stays deterministic and keyless. Local real-model acceptance remains
the release evidence until the hosted boundary is proven. This is a deliberate
delay of an optional CI feature, not a claim that the local release lacks
real-model validation. The Anthropic judge's separate live validation remains
deferred by user choice, and cloud deployment waits until other tasks finish.

## Alternatives considered

- Put a secret in the worker job environment: straightforward, but the worker
  executes repository-controlled code and nested agent commands.
- Reuse a copied ChatGPT CLI auth cache on a public repository runner: it is a
  credential artifact and is not the recommended public CI path.
- Run the Codex GitHub Action instead of HarnessFlow: protects a standalone
  Codex invocation but would not test the durable HarnessFlow run end to end.
