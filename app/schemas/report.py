from typing import Literal

from pydantic import BaseModel


class Hypothesis(BaseModel):
    cause: str
    confidence: Literal["low", "medium", "high"]
    evidence: list[str]


class InvestigationReport(BaseModel):
    summary: str
    hypotheses: list[Hypothesis]
    recommended_next_steps: list[str]
