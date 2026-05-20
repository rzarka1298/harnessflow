"""Temporal activity implementations for HarnessFlow workflows.

Activities are registered by DSL step-type name — ``llm_call``, ``retrieve``,
``tool_call``, ``verify`` — so the Go workflow function dispatches by name and
the wire format stays language-agnostic.

For Week 2 these activities ran as Go stubs inside apps/api. As of Week 3 the
real implementations live here and the Go stubs are removed.
"""
