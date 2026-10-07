from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import IncidentRepository
from app.db.session import get_session
from app.schemas.incident import IncidentCreate, IncidentDetail, IncidentOut, InvestigateResponse
from app.schemas.report import InvestigationReport
from app.services.investigation import InvestigationService

router = APIRouter(prefix="/incidents", tags=["incidents"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_investigation_service(request: Request) -> InvestigationService:
    state = request.app.state
    if getattr(state, "investigation_service", None) is None:
        state.investigation_service = state.build_investigation_service(request.app)
    return state.investigation_service


ServiceDep = Annotated[InvestigationService, Depends(get_investigation_service)]


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


@router.post("/{incident_id}/investigate", response_model=InvestigateResponse)
async def investigate_incident(incident_id: int, service: ServiceDep) -> InvestigateResponse:
    record = await service.investigate(incident_id)
    return InvestigateResponse(
        incident_id=incident_id,
        report_id=record.id,
        status="completed",
        report=InvestigationReport.model_validate(record.report_json),
    )
