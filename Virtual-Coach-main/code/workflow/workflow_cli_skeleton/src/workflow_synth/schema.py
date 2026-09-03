from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, RootModel

InputRef = Union[str, None]

class NodeConfig(BaseModel):
    """Node JSON schema (core fields)."""
    id: int = Field(..., ge=0)
    node_type: str = Field(..., min_length=1)
    node_name: str = Field(..., min_length=1)

    key_node: Optional[bool] = None
    msg_queue: Optional[bool] = None

    input_map: Dict[str, InputRef] = Field(default_factory=dict)
    choice_map: Dict[str, str] = Field(default_factory=dict)
    attrs: Dict[str, Any] = Field(default_factory=dict)

class WorkflowBody(BaseModel):
    start_node: str = Field(..., min_length=1)
    listen_at_start: bool = True
    input_parameters: Dict[str, Any] = Field(default_factory=dict)
    nodes: List[NodeConfig] = Field(default_factory=list)

class WorkflowFile(RootModel[Dict[str, WorkflowBody]]):
    """Root: { workflow_name: WorkflowBody }"""
    pass
