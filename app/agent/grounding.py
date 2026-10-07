from app.agent.errors import GroundingViolation
from app.schemas.report import InvestigationReport


def validate_grounding(report: InvestigationReport, evidence: list[str]) -> None:
    """Require every cited line to exactly match a line the tools returned."""
    collected = set(evidence)
    for hypothesis in report.hypotheses:
        for line in hypothesis.evidence:
            if line not in collected:
                raise GroundingViolation(f"Report cites evidence the tools did not return: {line!r}")
