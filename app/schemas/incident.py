from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

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


class IncidentDetail(IncidentOut):
    latest_report: None = None
