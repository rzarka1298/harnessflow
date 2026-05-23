# apps/eval-runner

HarnessFlow's evaluation framework. Runs a workflow over a dataset, scores each
case, and reports aggregate quality + cost/latency. See ADR-0006 for why this is
in-house rather than deepeval/ragas, and `Project-Documentation/evals/`.

```bash
uv sync
# Score a workflow over a dataset (api + worker must be running):
uv run harnessflow-eval --workflow-id <id> --dataset research-assistant
uv run pytest        # scorer + aggregation unit tests (offline)
```

Scorers: `exact_match`, `embedding_similarity` (all-MiniLM cosine, offline),
`llm_judge` (reuses the worker's LLMClient). Latency and cost are reported from
each run's metrics. Reporters: markdown (for PR comments) and JSON.
