from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Incident, InvestigationReportRecord
from app.schemas.investigation import InvestigationResult


class IncidentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, title: str, description: str) -> Incident:
        incident = Incident(title=title, description=description, status="created")
        self._session.add(incident)
        await self._session.flush()
        return incident

    async def get(self, incident_id: int) -> Incident | None:
        return await self._session.get(Incident, incident_id)

    async def save_report(
        self, incident_id: int, result: InvestigationResult, model_name: str
    ) -> InvestigationReportRecord:
        """Insert the report and mark the incident completed in the caller's transaction."""
        incident = await self._session.get(Incident, incident_id)
        incident.status = "completed"
        record = InvestigationReportRecord(
            incident_id=incident_id,
            report_json=result.report.model_dump(mode="json"),
            evidence_json=result.evidence,
            tool_calls_json=[call.model_dump(mode="json") for call in result.tool_calls],
            model_name=model_name,
        )
        self._session.add(record)
        await self._session.flush()
        return record

    async def latest_report(self, incident_id: int) -> InvestigationReportRecord | None:
        """The committed report with the highest ID, i.e. the most recently saved one."""
        statement = (
            select(InvestigationReportRecord)
            .where(InvestigationReportRecord.incident_id == incident_id)
            .order_by(InvestigationReportRecord.id.desc())
            .limit(1)
        )
        return await self._session.scalar(statement)

    async def list_reports(self, incident_id: int) -> list[InvestigationReportRecord]:
        """Every saved report for the incident, oldest first."""
        statement = (
            select(InvestigationReportRecord)
            .where(InvestigationReportRecord.incident_id == incident_id)
            .order_by(InvestigationReportRecord.id)
        )
        return list(await self._session.scalars(statement))
