from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.agent.graph import InvestigationLimits, build_investigator
from app.agent.models import ChatModels, build_chat_models
from app.api import health, incidents
from app.api.errors import register_error_handlers
from app.config import Settings
from app.db.session import create_sessionmaker
from app.services.investigation import InvestigationService


def create_app(
    settings: Settings | None = None, chat_models: ChatModels | None = None
) -> FastAPI:
    """Compose the app. Tests pass `chat_models`; production builds them from settings."""
    settings = settings or Settings()

    def build_investigation_service(app: FastAPI) -> InvestigationService:
        models = chat_models or build_chat_models(settings)
        return InvestigationService(
            sessionmaker=app.state.sessionmaker,
            investigator=build_investigator(
                agent_model=models.agent,
                report_model=models.report,
                limits=InvestigationLimits.from_settings(settings),
            ),
            model_name=settings.llm_model,
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.sessionmaker = create_sessionmaker(settings)
        app.state.build_investigation_service = build_investigation_service
        yield
        await app.state.sessionmaker.kw["bind"].dispose()

    app = FastAPI(title="incident-agent-runtime", lifespan=lifespan)
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(incidents.router)
    return app
