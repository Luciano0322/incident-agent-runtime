from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

Text = Annotated[str, StringConstraints(strip_whitespace=True)]


class IncidentCreate(BaseModel):
    title: Text
    description: Text


class IncidentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    status: Literal["created", "completed"]


class IncidentDetail(IncidentOut):
    latest_report: None = None
