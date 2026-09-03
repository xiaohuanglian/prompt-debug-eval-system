from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class TraceStep(BaseModel):
    iteration: int = Field(..., ge=0)
    summary: str
    retrieved: List[Dict[str, Any]] = Field(default_factory=list)
    selected_nodes: List[Dict[str, Any]] = Field(default_factory=list)
    validation: Dict[str, Any] = Field(default_factory=dict)
    next_queries: List[Dict[str, Any]] = Field(default_factory=list)

class DecisionTrace(BaseModel):
    run_id: str
    requirement: str
    steps: List[TraceStep] = Field(default_factory=list)
    final_summary: Optional[str] = None
