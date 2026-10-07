from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import IncidentRepository
from app.db.session import get_session
from app.schemas.incident import IncidentCreate, IncidentDetail, IncidentOut

router = APIRouter(prefix="/incidents", tags=["incidents"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=IncidentOut)
async def create_incident(payload: IncidentCreate, session: SessionDep) -> IncidentOut:
    async with session.begin():
        incident = await IncidentRepository(session).create(
            title=payload.title, description=payload.description
        )
    return IncidentOut.model_validate(incident)


@router.get("/{incident_id}", response_model=IncidentDetail)
async def get_incident(incident_id: int, session: SessionDep) -> IncidentDetail:
    incident = await IncidentRepository(session).get(incident_id)
    if incident is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Incident not found")
    return IncidentDetail.model_validate(incident)
