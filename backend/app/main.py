from fastapi import FastAPI

from app.api.agent_sync import router as agent_sync_router
from app.api.health import router as health_router
from app.core.config import settings
from app.core.errors import register_error_handlers

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
)

register_error_handlers(app)

app.include_router(health_router)
app.include_router(agent_sync_router)
