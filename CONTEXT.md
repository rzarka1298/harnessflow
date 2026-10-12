# HarnessFlow

A local coding harness that turns product requirements into a reviewed branch with recorded acceptance evidence.

## Language

**Project**:
A repository paired with a product requirements document. A project may have multiple successive runs.

**Project run**:
A bounded, resumable effort to satisfy a project's requirements and deliver a verified branch.
_Avoid_: Workflow run (reserved for the legacy YAML product)

**Coding attempt**:
One implementation or repair effort. Planning and independent review consume active time but are not coding attempts.

**Acceptance check**:
A concrete behavioral check linked to requirements and frozen before implementation begins.

**Completion evidence**:
Recorded passing acceptance results and independent review for the exact delivered revision. An agent's statement of success alone is not completion evidence.

**Blocked run**:
A run awaiting missing information, access, or resolution of repeated failures. Its work is retained for resumption.

**Exhausted run**:
A run that reached its coding-attempt or active-time limit. Further work requires an explicit limit extension.

**Verified branch**:
The run's deliverable after all planned tasks, acceptance checks and independent review pass. Publishing a pull request is optional; merging and deployment are separate decisions.

**Real-model acceptance run**:
An opt-in exercise of a project run against an actual coding model, followed by
commit-bound checks and an independent fixture verifier. It is distinct from
the deterministic test suite and can consume model usage.
