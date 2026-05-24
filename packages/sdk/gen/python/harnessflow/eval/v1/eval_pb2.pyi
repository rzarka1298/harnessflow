import datetime

from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class EvalStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    EVAL_STATUS_UNSPECIFIED: _ClassVar[EvalStatus]
    EVAL_STATUS_PENDING: _ClassVar[EvalStatus]
    EVAL_STATUS_RUNNING: _ClassVar[EvalStatus]
    EVAL_STATUS_COMPLETED: _ClassVar[EvalStatus]
    EVAL_STATUS_FAILED: _ClassVar[EvalStatus]
EVAL_STATUS_UNSPECIFIED: EvalStatus
EVAL_STATUS_PENDING: EvalStatus
EVAL_STATUS_RUNNING: EvalStatus
EVAL_STATUS_COMPLETED: EvalStatus
EVAL_STATUS_FAILED: EvalStatus

class ScorerScore(_message.Message):
    __slots__ = ("scorer", "score", "passed")
    SCORER_FIELD_NUMBER: _ClassVar[int]
    SCORE_FIELD_NUMBER: _ClassVar[int]
    PASSED_FIELD_NUMBER: _ClassVar[int]
    scorer: str
    score: float
    passed: bool
    def __init__(self, scorer: _Optional[str] = ..., score: _Optional[float] = ..., passed: _Optional[bool] = ...) -> None: ...

class EvalCaseResult(_message.Message):
    __slots__ = ("case_id", "run_id", "scores", "output_preview", "latency_ms", "cost_usd_cents")
    CASE_ID_FIELD_NUMBER: _ClassVar[int]
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    SCORES_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_PREVIEW_FIELD_NUMBER: _ClassVar[int]
    LATENCY_MS_FIELD_NUMBER: _ClassVar[int]
    COST_USD_CENTS_FIELD_NUMBER: _ClassVar[int]
    case_id: str
    run_id: str
    scores: _containers.RepeatedCompositeFieldContainer[ScorerScore]
    output_preview: str
    latency_ms: int
    cost_usd_cents: int
    def __init__(self, case_id: _Optional[str] = ..., run_id: _Optional[str] = ..., scores: _Optional[_Iterable[_Union[ScorerScore, _Mapping]]] = ..., output_preview: _Optional[str] = ..., latency_ms: _Optional[int] = ..., cost_usd_cents: _Optional[int] = ...) -> None: ...

class EvalRun(_message.Message):
    __slots__ = ("id", "workflow_id", "workflow_version", "dataset", "status", "created_at", "completed_at", "aggregate_scores", "overall_score", "seeds_per_case", "latency_p50_ms", "latency_p95_ms", "cost_total_usd_cents")
    ID_FIELD_NUMBER: _ClassVar[int]
    WORKFLOW_ID_FIELD_NUMBER: _ClassVar[int]
    WORKFLOW_VERSION_FIELD_NUMBER: _ClassVar[int]
    DATASET_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    COMPLETED_AT_FIELD_NUMBER: _ClassVar[int]
    AGGREGATE_SCORES_FIELD_NUMBER: _ClassVar[int]
    OVERALL_SCORE_FIELD_NUMBER: _ClassVar[int]
    SEEDS_PER_CASE_FIELD_NUMBER: _ClassVar[int]
    LATENCY_P50_MS_FIELD_NUMBER: _ClassVar[int]
    LATENCY_P95_MS_FIELD_NUMBER: _ClassVar[int]
    COST_TOTAL_USD_CENTS_FIELD_NUMBER: _ClassVar[int]
    id: str
    workflow_id: str
    workflow_version: int
    dataset: str
    status: EvalStatus
    created_at: _timestamp_pb2.Timestamp
    completed_at: _timestamp_pb2.Timestamp
    aggregate_scores: _containers.RepeatedCompositeFieldContainer[ScorerScore]
    overall_score: float
    seeds_per_case: int
    latency_p50_ms: int
    latency_p95_ms: int
    cost_total_usd_cents: int
    def __init__(self, id: _Optional[str] = ..., workflow_id: _Optional[str] = ..., workflow_version: _Optional[int] = ..., dataset: _Optional[str] = ..., status: _Optional[_Union[EvalStatus, str]] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., completed_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., aggregate_scores: _Optional[_Iterable[_Union[ScorerScore, _Mapping]]] = ..., overall_score: _Optional[float] = ..., seeds_per_case: _Optional[int] = ..., latency_p50_ms: _Optional[int] = ..., latency_p95_ms: _Optional[int] = ..., cost_total_usd_cents: _Optional[int] = ...) -> None: ...

class RunEvalRequest(_message.Message):
    __slots__ = ("workflow_id", "dataset", "seeds_per_case")
    WORKFLOW_ID_FIELD_NUMBER: _ClassVar[int]
    DATASET_FIELD_NUMBER: _ClassVar[int]
    SEEDS_PER_CASE_FIELD_NUMBER: _ClassVar[int]
    workflow_id: str
    dataset: str
    seeds_per_case: int
    def __init__(self, workflow_id: _Optional[str] = ..., dataset: _Optional[str] = ..., seeds_per_case: _Optional[int] = ...) -> None: ...

class RunEvalResponse(_message.Message):
    __slots__ = ("eval_run_id",)
    EVAL_RUN_ID_FIELD_NUMBER: _ClassVar[int]
    eval_run_id: str
    def __init__(self, eval_run_id: _Optional[str] = ...) -> None: ...

class GetEvalRunRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class GetEvalRunResponse(_message.Message):
    __slots__ = ("eval_run", "case_results")
    EVAL_RUN_FIELD_NUMBER: _ClassVar[int]
    CASE_RESULTS_FIELD_NUMBER: _ClassVar[int]
    eval_run: EvalRun
    case_results: _containers.RepeatedCompositeFieldContainer[EvalCaseResult]
    def __init__(self, eval_run: _Optional[_Union[EvalRun, _Mapping]] = ..., case_results: _Optional[_Iterable[_Union[EvalCaseResult, _Mapping]]] = ...) -> None: ...

class ListEvalRunsRequest(_message.Message):
    __slots__ = ("workflow_id", "page_size", "page_token")
    WORKFLOW_ID_FIELD_NUMBER: _ClassVar[int]
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    workflow_id: str
    page_size: int
    page_token: str
    def __init__(self, workflow_id: _Optional[str] = ..., page_size: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListEvalRunsResponse(_message.Message):
    __slots__ = ("eval_runs", "next_page_token")
    EVAL_RUNS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    eval_runs: _containers.RepeatedCompositeFieldContainer[EvalRun]
    next_page_token: str
    def __init__(self, eval_runs: _Optional[_Iterable[_Union[EvalRun, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...
