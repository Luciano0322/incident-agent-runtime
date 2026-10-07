import pytest

from app.agent.errors import GroundingViolation
from app.agent.grounding import validate_grounding
from app.schemas.report import Hypothesis, InvestigationReport
from app.tools.logs import query_logs


def report_citing(*lines: str) -> InvestigationReport:
    return InvestigationReport(
        summary="Checkout latency may be related to the database.",
        hypotheses=[Hypothesis(cause="Database issue", confidence="medium", evidence=list(lines))],
        recommended_next_steps=["Inspect active database connections"],
    )


def test_exact_lines_returned_by_the_tool_are_accepted():
    evidence = query_logs(service="checkout")

    validate_grounding(
        report_citing(
            "14:21 checkout-api ERROR database connection timeout",
            "14:22 checkout-api ERROR connection pool exhausted",
        ),
        evidence,
    )


def test_paraphrased_line_is_rejected():
    evidence = query_logs(service="checkout")

    with pytest.raises(GroundingViolation):
        validate_grounding(report_citing("checkout-api ERROR connection pool exhausted"), evidence)


def test_line_from_a_service_that_was_not_queried_is_rejected():
    evidence = query_logs(service="checkout")

    with pytest.raises(GroundingViolation):
        validate_grounding(report_citing("15:01 payment-api ERROR upstream timeout"), evidence)


def test_line_excluded_by_keyword_is_rejected():
    evidence = query_logs(service="checkout", keyword="pool")

    with pytest.raises(GroundingViolation):
        validate_grounding(
            report_citing("14:21 checkout-api ERROR database connection timeout"), evidence
        )


def test_incident_description_is_not_evidence():
    evidence = query_logs(service="checkout")

    with pytest.raises(GroundingViolation):
        validate_grounding(
            report_citing("Checkout API latency increased significantly after 14:20."), evidence
        )


def test_report_without_hypotheses_is_accepted_when_no_evidence_was_collected():
    report = InvestigationReport(
        summary="No log evidence was collected for this incident.",
        hypotheses=[],
        recommended_next_steps=["Identify the affected service and query its logs"],
    )

    validate_grounding(report, evidence=[])
