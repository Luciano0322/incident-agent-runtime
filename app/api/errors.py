from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.agent.errors import DeadlineExceeded, InvestigationError
from app.services.investigation import IncidentNotFound


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(IncidentNotFound)
    async def incident_not_found(request: Request, exc: IncidentNotFound) -> JSONResponse:
        return JSONResponse({"detail": "Incident not found"}, status.HTTP_404_NOT_FOUND)

    @app.exception_handler(DeadlineExceeded)
    async def investigation_timed_out(request: Request, exc: DeadlineExceeded) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status.HTTP_504_GATEWAY_TIMEOUT)

    @app.exception_handler(InvestigationError)
    async def investigation_failed(request: Request, exc: InvestigationError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status.HTTP_502_BAD_GATEWAY)
