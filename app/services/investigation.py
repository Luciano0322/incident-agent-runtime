from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agent.graph import Investigator
from app.db.models import InvestigationReportRecord
from app.db.repositories import IncidentRepository
from app.schemas.investigation import InvestigationInput


class InvestigationService:
    """Load an incident snapshot, investigate outside any transaction, then save."""

    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
        investigator: Investigator,
        model_name: str,
    ) -> None:
        self._sessionmaker = sessionmaker
        self._investigator = investigator
        self._model_name = model_name

    async def investigate(self, incident_id: int) -> InvestigationReportRecord:
        async with self._sessionmaker() as session:
            incident = await IncidentRepository(session).get(incident_id)
            snapshot = InvestigationInput(
                incident_id=incident.id, title=incident.title, description=incident.description
            )

        result = await self._investigator.investigate(snapshot)

        async with self._sessionmaker() as session, session.begin():
            return await IncidentRepository(session).save_report(
                incident_id, result, self._model_name
            )
