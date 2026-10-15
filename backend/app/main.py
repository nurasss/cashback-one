from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin import router as admin_router
from app.api.admin_auth import router as admin_auth_router
from app.api.agent_pos import router as agent_pos_router
from app.api.agent_sync import router as agent_sync_router
from app.api.auth import router as auth_router
from app.api.customer_app import router as customer_app_router
from app.api.customer_wallet import router as customer_wallet_router
from app.api.health import router as health_router
from app.api.webhooks import router as webhooks_router
from app.core.config import settings
from app.core.errors import register_error_handlers
from app.core.logging import RequestCorrelationMiddleware, configure_logging
from app.core.request_limits import AdminBusinessPayloadLimitMiddleware
from app.services.rate_limiter import close_redis_client, get_redis_client

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    if settings.app_env.lower() != "test" and settings.redis_url:
        app.state.redis = get_redis_client()
    yield
    await close_redis_client()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs" if settings.app_env.lower() != "production" or settings.debug else None,
    redoc_url="/redoc" if settings.app_env.lower() != "production" or settings.debug else None,
    openapi_url="/openapi.json" if settings.app_env.lower() != "production" or settings.debug else None,
    lifespan=lifespan,
)
register_error_handlers(app)
app.add_middleware(AdminBusinessPayloadLimitMiddleware, max_bytes=16_384)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.admin_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-Admin-Request"],
    max_age=600,
)
app.add_middleware(RequestCorrelationMiddleware)

app.include_router(health_router)
app.include_router(agent_sync_router)
app.include_router(agent_pos_router)
app.include_router(auth_router)
app.include_router(customer_wallet_router)
app.include_router(customer_app_router)
app.include_router(webhooks_router)
app.include_router(admin_auth_router, prefix="/admin")
app.include_router(admin_router, prefix="/admin")
