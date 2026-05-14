# ADR-0007: Use contextual bandits, not deep RL, for retry-policy learning

Date: 2026-05-14
Status: Proposed (target: week 13)

## Context

The week-13 research extension is a learned retry policy: replace the YAML's static `retries: 3` rules with a service that observes historical workflow runs and recommends retry actions per-step. The PRD framed this as "RL-based retry optimization."

A portfolio project will produce, generously, a few thousand workflow runs over its lifetime. Deep RL (DQN, PPO, etc.) needs many orders of magnitude more data than that. Misapplying deep RL is worse than not applying RL — it signals the candidate doesn't understand the data regime.

Contextual bandits (specifically Thompson sampling) are the right tool for the actual problem: small action space (retry-same, retry-other-model, retry-with-reduced-context, fail-fast), reward observable per-arm (success rate + latency + cost), modest data requirements.

## Decision

**Use contextual bandits with per-(workflow, step) Thompson-sampling models.** Train in batch nightly from the `workflow_steps` table. Serve recommendations via a Connect RPC `RetryPolicyService.Recommend`.

Frame the entire feature publicly as "learned retry policy" or "bandit-based retry optimization." Be explicit in the writeup that deep RL would be inappropriate here — the *honesty* is itself the signal.

## Consequences

- **Enables:** a real, working, learned policy with a clean A/B comparison story (same eval set, learned beats static on cost or latency). The bandit is what AI-infra teams actually deploy for this class of problem.
- **Forecloses:** the "I used deep RL" bullet. Acceptable: misusing deep RL is a negative signal at the target companies.
- **Operational:** one Python service (`apps/policy-learner`). Postgres is the feature store. No separate model server.
- **Recruiter signal:** "I picked contextual bandits because deep RL is inappropriate for the data regime" is a stronger answer to "tell me about an ML decision you made" than "I trained PPO and it learned a policy."

## Alternatives considered

- **Deep RL (DQN/PPO).** Rejected: data-regime mismatch.
- **Hand-tuned heuristics.** Rejected: gives up the learning story; lower signal.
- **No retry learner; expand declarative fallback graph instead.** Considered. The fallback graph already exists ([ADR-0003](./0003-skip-langchain.md)); the bandit adds the *learning* signal on top.
- **Multi-armed bandit (non-contextual).** Rejected: ignores per-step features (model, prompt-type, error-class), which is most of the signal.
