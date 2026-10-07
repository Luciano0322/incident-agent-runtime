from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.schemas.investigation import ToolCallRecord
from app.schemas.report import InvestigationReport

TITLE_MAX_LENGTH = 200
DESCRIPTION_MAX_LENGTH = 5000

Title = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=TITLE_MAX_LENGTH)
]
Description = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=DESCRIPTION_MAX_LENGTH),
]


class IncidentCreate(BaseModel):
    title: Title
    description: Description


class IncidentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    status: Literal["created", "completed"]


class SavedReport(BaseModel):
    id: int
    created_at: datetime
    report: InvestigationReport
    evidence: list[str]
    tool_calls: list[ToolCallRecord]
    model_name: str


class IncidentDetail(IncidentOut):
    latest_report: SavedReport | None


class InvestigateResponse(BaseModel):
    incident_id: int
    report_id: int
    status: Literal["completed"]
    report: InvestigationReport
