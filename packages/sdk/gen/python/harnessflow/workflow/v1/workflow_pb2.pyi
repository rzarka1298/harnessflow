import datetime

from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class WorkflowStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    WORKFLOW_STATUS_UNSPECIFIED: _ClassVar[WorkflowStatus]
    WORKFLOW_STATUS_DRAFT: _ClassVar[WorkflowStatus]
    WORKFLOW_STATUS_ACTIVE: _ClassVar[WorkflowStatus]
    WORKFLOW_STATUS_ARCHIVED: _ClassVar[WorkflowStatus]
WORKFLOW_STATUS_UNSPECIFIED: WorkflowStatus
WORKFLOW_STATUS_DRAFT: WorkflowStatus
WORKFLOW_STATUS_ACTIVE: WorkflowStatus
WORKFLOW_STATUS_ARCHIVED: WorkflowStatus

class Workflow(_message.Message):
    __slots__ = ("id", "name", "version", "description", "yaml_source", "status", "created_at", "updated_at")
    ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    YAML_SOURCE_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    id: str
    name: str
    version: int
    description: str
    yaml_source: str
    status: WorkflowStatus
    created_at: _timestamp_pb2.Timestamp
    updated_at: _timestamp_pb2.Timestamp
    def __init__(self, id: _Optional[str] = ..., name: _Optional[str] = ..., version: _Optional[int] = ..., description: _Optional[str] = ..., yaml_source: _Optional[str] = ..., status: _Optional[_Union[WorkflowStatus, str]] = ..., created_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ..., updated_at: _Optional[_Union[datetime.datetime, _timestamp_pb2.Timestamp, _Mapping]] = ...) -> None: ...

class CreateWorkflowRequest(_message.Message):
    __slots__ = ("yaml_source",)
    YAML_SOURCE_FIELD_NUMBER: _ClassVar[int]
    yaml_source: str
    def __init__(self, yaml_source: _Optional[str] = ...) -> None: ...

class CreateWorkflowResponse(_message.Message):
    __slots__ = ("workflow",)
    WORKFLOW_FIELD_NUMBER: _ClassVar[int]
    workflow: Workflow
    def __init__(self, workflow: _Optional[_Union[Workflow, _Mapping]] = ...) -> None: ...

class GetWorkflowRequest(_message.Message):
    __slots__ = ("id",)
    ID_FIELD_NUMBER: _ClassVar[int]
    id: str
    def __init__(self, id: _Optional[str] = ...) -> None: ...

class GetWorkflowResponse(_message.Message):
    __slots__ = ("workflow",)
    WORKFLOW_FIELD_NUMBER: _ClassVar[int]
    workflow: Workflow
    def __init__(self, workflow: _Optional[_Union[Workflow, _Mapping]] = ...) -> None: ...

class ListWorkflowsRequest(_message.Message):
    __slots__ = ("page_size", "page_token")
    PAGE_SIZE_FIELD_NUMBER: _ClassVar[int]
    PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    page_size: int
    page_token: str
    def __init__(self, page_size: _Optional[int] = ..., page_token: _Optional[str] = ...) -> None: ...

class ListWorkflowsResponse(_message.Message):
    __slots__ = ("workflows", "next_page_token")
    WORKFLOWS_FIELD_NUMBER: _ClassVar[int]
    NEXT_PAGE_TOKEN_FIELD_NUMBER: _ClassVar[int]
    workflows: _containers.RepeatedCompositeFieldContainer[Workflow]
    next_page_token: str
    def __init__(self, workflows: _Optional[_Iterable[_Union[Workflow, _Mapping]]] = ..., next_page_token: _Optional[str] = ...) -> None: ...

class RunWorkflowRequest(_message.Message):
    __slots__ = ("workflow_id", "inputs")
    class InputsEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: str
        def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ...) -> None: ...
    WORKFLOW_ID_FIELD_NUMBER: _ClassVar[int]
    INPUTS_FIELD_NUMBER: _ClassVar[int]
    workflow_id: str
    inputs: _containers.ScalarMap[str, str]
    def __init__(self, workflow_id: _Optional[str] = ..., inputs: _Optional[_Mapping[str, str]] = ...) -> None: ...

class RunWorkflowResponse(_message.Message):
    __slots__ = ("run_id",)
    RUN_ID_FIELD_NUMBER: _ClassVar[int]
    run_id: str
    def __init__(self, run_id: _Optional[str] = ...) -> None: ...
