"""create investigation_reports

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "investigation_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("incident_id", sa.Integer(), sa.ForeignKey("incidents.id"), nullable=False),
        sa.Column("report_json", JSONB(), nullable=False),
        sa.Column("evidence_json", JSONB(), nullable=False),
        sa.Column("tool_calls_json", JSONB(), nullable=False),
        sa.Column("model_name", sa.String(200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_investigation_reports_incident_id", "investigation_reports", ["incident_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_investigation_reports_incident_id", "investigation_reports")
    op.drop_table("investigation_reports")
