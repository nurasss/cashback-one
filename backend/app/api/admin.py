import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin_deps import AdminScope, get_admin_scope, require_admin_origin
from app.db.session import get_session
from app.models.admin import AdminUser
from app.schemas.admin import (
    AdminIdentity,
    AdminMeResponse,
    AgentItem,
    AuditItem,
    BusinessDetail,
    BusinessListItem,
    CardDetail,
    CardListItem,
    CardSearchRequest,
    DashboardResponse,
    Page,
    PaginationParams,
    UserDetail,
    UserListItem,
    UserSearchRequest,
)
from app.services.admin_auth import authenticate_admin
from app.services.admin_queries import (
    admin_identity,
    dashboard,
    get_agent,
    get_business,
    get_card_detail,
    get_user_detail,
    list_agents,
    list_audit_logs,
    list_businesses,
    search_cards,
    search_users,
)

router = APIRouter(dependencies=[Depends(require_admin_origin)])


@router.get("/me", response_model=AdminMeResponse)
async def admin_me(
    admin: Annotated[AdminUser, Depends(authenticate_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> AdminMeResponse:
    return AdminMeResponse(admin=AdminIdentity.model_validate(await admin_identity(db, admin)))


@router.get("/dashboard", response_model=DashboardResponse)
async def admin_dashboard(
    scope: Annotated[AdminScope, Depends(get_admin_scope)],
    db: Annotated[AsyncSession, Depends(get_session)],
    business_id: uuid.UUID | None = None,
    start: Annotated[datetime | None, Query(alias="from")] = None,
    end: Annotated[datetime | None, Query(alias="to")] = None,
) -> DashboardResponse:
    return await dashboard(db, scope, business_id, start, end)


@router.get("/businesses", response_model=Page[BusinessListItem])
async def admin_businesses(
    scope: Annotated[AdminScope, Depends(get_admin_scope)],
    db: Annotated[AsyncSession, Depends(get_session)],
    page: Annotated[PaginationParams, Depends()],
) -> Page[BusinessListItem]:
    scope.require_superadmin()
    return await list_businesses(db, page.limit, page.offset)


@router.get("/businesses/{business_id}", response_model=BusinessDetail)
async def admin_business_detail(
    business_id: uuid.UUID,
    scope: Annotated[AdminScope, Depends(get_admin_scope)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> BusinessDetail:
    scope.require_superadmin()
    return await get_business(db, business_id)


@router.get("/agents", response_model=Page[AgentItem])
async def admin_agents(
    scope: Annotated[AdminScope, Depends(get_admin_scope)],
    db: Annotated[AsyncSession, Depends(get_session)],
    page: Annotated[PaginationParams, Depends()],
    business_id: uuid.UUID | None = None,
) -> Page[AgentItem]:
    return await list_agents(db, scope, business_id, page.limit, page.offset)


@router.get("/agents/{agent_id}", response_model=AgentItem)
async def admin_agent_detail(
    agent_id: uuid.UUID,
    scope: Annotated[AdminScope, Depends(get_admin_scope)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> AgentItem:
    return await get_agent(db, scope, agent_id)


@router.post("/cards/search", response_model=Page[CardListItem])
async def admin_search_cards(
    body: CardSearchRequest,
    scope: Annotated[AdminScope, Depends(get_admin_scope)],
    db: Annotated[AsyncSession, Depends(get_session)],
    page: Annotated[PaginationParams, Depends()],
) -> Page[CardListItem]:
    return await search_cards(
        db, scope, body.barcode, body.phone, body.business_id, page.limit, page.offset
    )


@router.get("/cards/{card_id}", response_model=CardDetail)
async def admin_card_detail(
    card_id: uuid.UUID,
    scope: Annotated[AdminScope, Depends(get_admin_scope)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> CardDetail:
    return await get_card_detail(db, scope, card_id)


@router.post("/users/search", response_model=Page[UserListItem])
async def admin_search_users(
    body: UserSearchRequest,
    scope: Annotated[AdminScope, Depends(get_admin_scope)],
    db: Annotated[AsyncSession, Depends(get_session)],
    page: Annotated[PaginationParams, Depends()],
) -> Page[UserListItem]:
    return await search_users(db, scope, body.phone, body.business_id, page.limit, page.offset)


@router.get("/users/{user_id}", response_model=UserDetail)
async def admin_user_detail(
    user_id: uuid.UUID,
    scope: Annotated[AdminScope, Depends(get_admin_scope)],
    db: Annotated[AsyncSession, Depends(get_session)],
    page: Annotated[PaginationParams, Depends()],
    business_id: uuid.UUID | None = None,
) -> UserDetail:
    return await get_user_detail(db, scope, user_id, business_id, page.limit, page.offset)


@router.get("/audit", response_model=Page[AuditItem])
async def admin_audit(
    scope: Annotated[AdminScope, Depends(get_admin_scope)],
    db: Annotated[AsyncSession, Depends(get_session)],
    page: Annotated[PaginationParams, Depends()],
) -> Page[AuditItem]:
    # AuditLog has no tenant key; never expose it to a business manager.
    scope.require_superadmin()
    return await list_audit_logs(db, page.limit, page.offset)
