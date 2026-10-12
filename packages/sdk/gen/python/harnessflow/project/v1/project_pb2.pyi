import datetime

from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class Project(_message.Message):
    __slots__ = ("id", "name", "repository_path", "prd", "created_at")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    REPOSITORY_PATH_FIELD_NUMBER: _ClassVar[int]
    PRD_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    id: str
    name: str
    repository_path: str
    prd: str
    created_at: _timestamp_pb2.Timestamp
    def __init__(self, id: _Optional[str] = ..., name: _Optional[str] = ..., repository_path: _Optional[str] = ..., prd: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class ProjectRun(_message.Message):
    __slots__ = ("id", "project_id", "status", "reason", "snapshot_json", "created_at", "updated_at")
    ID_FIELD_NUMBER: _ClassVar[int]
    PROJECT_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    SNAPSHOT_JSON_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    id: str
    project_id: str
    status: str
    reason: str
    snapshot_json: str
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    def __init__(self, id: _Optional[str] = ..., project_id: _Optional[str] = ..., status: _Optional[str] = ..., reason: _Optional[str] = ..., snapshot_json: _Optional[str] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class CreateProjectRequest(_message.Message):
    __slots__ = ("name", "repository_path", "prd")
    NAME_FIELD_NUMBER: _ClassVar[int]
    REPOSITORY_PATH_FIELD_NUMBER: _ClassVar[int]
    PRD_FIELD_NUMBER: _ClassVar[int]
    name: str
    repository_path: str
    prd: str
    def __init__(self, name: _Optional[str] = ..., repository_path: _Optional[str] = ..., prd: _Optional[str] = ...) -> None: ...

class CreateProjectResponse(_message.Message):
    __slots__ = ("project",)
    PROJECT_FIELD_NUMBER: _ClassVar[int]
    project: Project
    def __init__(self, project: _Optional[_Union[Project, _Mapping]] = ...) -> None: ...

class GetProjectRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class GetProjectResponse(_message.Message):
    __slots__ = ("project",)
    PROJECT_FIELD_NUMBER: _ClassVar[int]
    project: Project
    def __init__(self, project: _Optional[_Union[Project, _Mapping]] = ...) -> None: ...

class ListProjectsRequest(_message.Message):
    __slots__ = ("page_size", "page_token")
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    page_size: int
    page_token: str
    def __init__(self, page_size: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListProjectsResponse(_message.Message):
    __slots__ = ("projects", "next_page_token")
    PROJECTS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    projects: _containers.RepeatedCompositeFieldContainer[Project]
    next_page_token: str
    def __init__(self, projects: _Optional[_Iterable[_Union[Project, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class StartRunRequest(_message.Message):
    __slots__ = ("project_id", "max_attempts", "max_duration_seconds", "model", "request_pr")
    PROJECT_ID_FIELD_NUMBER: _ClassVar[int]
    MAX_ATTEMPTS_FIELD_NUMBER: _ClassVar[int]
    MAX_DURATION_SECONDS_FIELD_NUMBER: _ClassVar[int]
    MODEL_FIELD_NUMBER: _ClassVar[int]
    REQUEST_PR_FIELD_NUMBER: _ClassVar[int]
    project_id: str
    max_attempts: int
    max_duration_seconds: int
    model: str
    request_pr: bool
    def __init__(self, project_id: _Optional[str] = ..., max_attempts: _Optional[int] = ..., max_duration_seconds: _Optional[int] = ..., model: _Optional[str] = ..., request_pr: _Optional[bool] = ...) -> None: ...

class StartRunResponse(_message.Message):
    __slots__ = ("run",)
    RUN_FIELD_NUMBER: _ClassVar[int]
    run: ProjectRun
    def __init__(self, run: _Optional[_Union[ProjectRun, _Mapping]] = ...) -> None: ...

class GetRunRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class GetRunResponse(_message.Message):
    __slots__ = ("run",)
    RUN_FIELD_NUMBER: _ClassVar[int]
    run: ProjectRun
    def __init__(self, run: _Optional[_Union[ProjectRun, _Mapping]] = ...) -> None: ...

class ListRunsRequest(_message.Message):
    __slots__ = ("project_id", "page_size", "page_token")
    PROJECT_ID_FIELD_NUMBER: _ClassVar[int]
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    project_id: str
    page_size: int
    page_token: str
    def __init__(self, project_id: _Optional[str] = ..., page_size: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListRunsResponse(_message.Message):
    __slots__ = ("runs", "next_page_token")
    RUNS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    runs: _containers.RepeatedCompositeFieldContainer[ProjectRun]
    next_page_token: str
    def __init__(self, runs: _Optional[_Iterable[_Union[ProjectRun, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class ControlRunRequest(_message.Message):
    __slots__ = ("run_id", "action", "clarification", "additional_attempts", "additional_seconds")
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    CLARIFICATION_FIELD_NUMBER: _ClassVar[int]
    ADDITIONAL_ATTEMPTS_FIELD_NUMBER: _ClassVar[int]
    ADDITIONAL_SECONDS_FIELD_NUMBER: _ClassVar[int]
    run_id: str
    action: str
    clarification: str
    additional_attempts: int
    additional_seconds: int
    def __init__(self, run_id: _Optional[str] = ..., action: _Optional[str] = ..., clarification: _Optional[str] = ..., additional_attempts: _Optional[int] = ..., additional_seconds: _Optional[int] = ...) -> None: ...

class ControlRunResponse(_message.Message):
    __slots__ = ("run",)
    RUN_FIELD_NUMBER: _ClassVar[int]
    run: ProjectRun
    def __init__(self, run: _Optional[_Union[ProjectRun, _Mapping]] = ...) -> None: ...

class GetArtifactsRequest(_message.Message):
    __slots__ = ("run_id",)
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    run_id: str
    def __init__(self, run_id: _Optional[str] = ...) -> None: ...

class GetArtifactsResponse(_message.Message):
    __slots__ = ("snapshot_json",)
    SNAPSHOT_JSON_FIELD_NUMBER: _ClassVar[int]
    snapshot_json: str
    def __init__(self, snapshot_json: _Optional[str] = ...) -> None: ...
