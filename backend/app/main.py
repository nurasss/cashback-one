from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.agent_sync import router as agent_sync_router
from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.core.config import settings
from app.core.errors import register_error_handlers
from app.services.rate_limiter import close_redis_client, get_redis_client


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Lifespan startup: initialize shared Redis client in production/development
    if settings.app_env.lower() != "test" and settings.redis_url:
        app.state.redis = get_redis_client()
    yield
    # Lifespan shutdown: close shared Redis connections gracefully
    await close_redis_client()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

register_error_handlers(app)

app.include_router(health_router)
app.include_router(agent_sync_router)
app.include_router(auth_router)


