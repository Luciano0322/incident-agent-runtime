import pytest
from pydantic import ValidationError

from app.schemas.report import InvestigationReport

PROPOSAL_EXAMPLE = {
    "summary": "Checkout latency may be related to database connection pool exhaustion.",
    "hypotheses": [
        {
            "cause": "Database connection pool exhaustion",
            "confidence": "high",
            "evidence": [
                "14:21 checkout-api ERROR database connection timeout",
                "14:22 checkout-api ERROR connection pool exhausted",
            ],
        }
    ],
    "recommended_next_steps": [
        "Inspect active database connections",
        "Check connection pool configuration",
    ],
}


def test_proposal_example_is_a_valid_report():
    report = InvestigationReport.model_validate(PROPOSAL_EXAMPLE)

    assert report.hypotheses[0].confidence == "high"


def test_confidence_outside_low_medium_high_is_rejected():
    invalid = {
        **PROPOSAL_EXAMPLE,
        "hypotheses": [{**PROPOSAL_EXAMPLE["hypotheses"][0], "confidence": "certain"}],
    }

    with pytest.raises(ValidationError, match="confidence"):
        InvestigationReport.model_validate(invalid)


@pytest.mark.parametrize("missing", ["summary", "hypotheses", "recommended_next_steps"])
def test_report_missing_required_field_is_rejected(missing):
    invalid = {k: v for k, v in PROPOSAL_EXAMPLE.items() if k != missing}

    with pytest.raises(ValidationError, match=missing):
        InvestigationReport.model_validate(invalid)
