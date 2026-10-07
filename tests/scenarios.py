"""Shared incident scenarios built from the fixed log fixture."""

from app.schemas.investigation import InvestigationInput

CHECKOUT = InvestigationInput(
    incident_id=1,
    title="Checkout API latency spike",
    description="Checkout API latency increased significantly after 14:20.",
)

CHECKOUT_LINES = [
    "14:21 checkout-api ERROR database connection timeout",
    "14:22 checkout-api ERROR connection pool exhausted",
    "14:24 checkout-api WARN retrying database request",
]

NO_EVIDENCE_REPORT = {
    "summary": "No log evidence was collected.",
    "hypotheses": [],
    "recommended_next_steps": ["Identify the affected service and query its logs"],
}

POOL_REPORT = {
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
    "recommended_next_steps": ["Inspect active database connections"],
}
