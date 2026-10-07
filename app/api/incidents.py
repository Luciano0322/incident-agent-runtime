from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import IncidentRepository
from app.db.session import get_session
from app.schemas.incident import IncidentCreate, IncidentOut

router = APIRouter(prefix="/incidents", tags=["incidents"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=IncidentOut)
async def create_incident(payload: IncidentCreate, session: SessionDep) -> IncidentOut:
    async with session.begin():
        incident = await IncidentRepository(session).create(
            title=payload.title, description=payload.description
        )
    return IncidentOut.model_validate(incident)
