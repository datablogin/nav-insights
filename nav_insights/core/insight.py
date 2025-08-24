from __future__ import annotations
from typing import Any, Dict, List
from pydantic import BaseModel, Field
from .actions import Action


class Section(BaseModel):
    title: str
    bullets: List[str] = Field(default_factory=list)
    metrics_highlights: Dict[str, Any] = Field(default_factory=dict)


class Insight(BaseModel):
    executive_summary: str
    sections: List[Section] = Field(default_factory=list)
    actions: List[Action] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
