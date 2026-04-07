"""
LangGraph shared state definition.

Every agent node reads from and writes to this TypedDict.
Values are plain dicts/lists (JSON-serializable) — Pydantic models
are serialized via .model_dump() on write and validated on read.
"""

from typing import Optional, List
from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    pdf_text: str
    extraction: Optional[dict]
    weaknesses: Optional[List[dict]]
    counterarguments: Optional[List[dict]]
    strategy: Optional[dict]
    error: Optional[str]
