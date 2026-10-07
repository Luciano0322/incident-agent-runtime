from typing import Any

from pydantic import BaseModel

from app.schemas.report import InvestigationReport


class InvestigationInput(BaseModel):
    incident_id: int
    title: str
    description: str


class ToolCallRecord(BaseModel):
    name: str
    args: dict[str, Any]


class InvestigationResult(BaseModel):
    report: InvestigationReport
    evidence: list[str]
    tool_calls: list[ToolCallRecord]
