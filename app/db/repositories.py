from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Incident


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
