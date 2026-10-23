import uuid
from datetime import datetime
from typing import Annotated, cast

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin_deps import AdminScope, get_admin_scope, require_admin_origin
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.db.session import get_session
from app.models.admin import AdminUser
from app.schemas.admin import (
    AdminIdentity,
    AdminMeResponse,
    AgentCommandResponse,
    AgentCommandStatus,
    AgentCreateRequest,
    AgentItem,
    AgentKeyDisclosureResponse,
    AgentRevokeResponse,
    AuditItem,
    BusinessCreatedResponse,
    BusinessCreateRequest,
    BusinessDetail,
    BusinessListItem,
    BusinessUpdateRequest,
    CardDetail,
    CardListItem,
    CardListPaginationParams,
    CardSearchRequest,
    CardUnbindResponse,
    CardUnbindStatus,
    DashboardResponse,
    ManagerAccessDisclosure,
    Page,
    PaginationParams,
    UserDetail,
    UserListItem,
    UserSearchRequest,
)
from app.schemas.admin_content import (
    ImageUploadResponse,
    NotificationAdminItem,
    NotificationCreateRequest,
    PromotionAdminItem,
    PromotionCreateRequest,
    PromotionUpdateRequest,
)
from app.services import admin_content
from app.services.admin_auth import authenticate_admin
from app.services.admin_mutations import (
    create_agent,
    create_business,
    request_full_resync,
    reset_or_create_business_manager,
    revoke_agent_access,
    rotate_agent_api_key,
    unbind_card,
    update_business,
)
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
    list_cards,
    search_cards,
    search_users,
)
from app.services.image_service import process_and_store_image
from app.services.media_storage import MediaStorage, get_media_storage

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


@router.post("/businesses", response_model=BusinessCreatedResponse, status_code=201)
async def admin_create_business(
    body: BusinessCreateRequest,
    scope: Annotated[AdminScope, Depends(get_admin_scope)],
    admin: Annotated[AdminUser, Depends(authenticate_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
    response: Response,
) -> BusinessCreatedResponse:
    scope.require_superadmin()
    response.headers["Cache-Control"] = "no-store"
    business, manager_access = await create_business(db, admin, body)
    detail = await get_business(db, business.id)
    return BusinessCreatedResponse(
        **detail.model_dump(),
        manager_access=manager_access,
    )


@router.post("/businesses/{business_id}/manager-access", response_model=ManagerAccessDisclosure)
async def admin_business_manager_access(
    business_id: uuid.UUID,
    scope: Annotated[AdminScope, Depends(get_admin_scope)],
    admin: Annotated[AdminUser, Depends(authenticate_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
    response: Response,
) -> ManagerAccessDisclosure:
    scope.require_superadmin()
    response.headers["Cache-Control"] = "no-store"
    return await reset_or_create_business_manager(db, admin, business_id)


@router.get("/businesses/{business_id}", response_model=BusinessDetail)
async def admin_business_detail(
    business_id: uuid.UUID,
    scope: Annotated[AdminScope, Depends(get_admin_scope)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> BusinessDetail:
    scope.require_superadmin()
    return await get_business(db, business_id)


@router.patch("/businesses/{business_id}", response_model=BusinessDetail)
async def admin_update_business(
    business_id: uuid.UUID,
    body: BusinessUpdateRequest,
    scope: Annotated[AdminScope, Depends(get_admin_scope)],
    admin: Annotated[AdminUser, Depends(authenticate_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[MediaStorage, Depends(get_media_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> BusinessDetail:
    scope.require_superadmin()
    business = await update_business(
        db, admin, business_id, body, storage=storage, settings=settings
    )
    return await get_business(db, business.id)


@router.get("/agents", response_model=Page[AgentItem])
async def admin_agents(
    scope: Annotated[AdminScope, Depends(get_admin_scope)],
    db: Annotated[AsyncSession, Depends(get_session)],
    page: Annotated[PaginationParams, Depends()],
    business_id: uuid.UUID | None = None,
) -> Page[AgentItem]:
    return await list_agents(db, scope, business_id, page.limit, page.offset)


@router.post("/agents", response_model=AgentKeyDisclosureResponse, status_code=201)
async def admin_create_agent(
    body: AgentCreateRequest,
    scope: Annotated[AdminScope, Depends(get_admin_scope)],
    admin: Annotated[AdminUser, Depends(authenticate_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> AgentKeyDisclosureResponse:
    scope.require_superadmin()
    agent, raw_key = await create_agent(db, admin, body.business_id)
    return AgentKeyDisclosureResponse(agent=await get_agent(db, scope, agent.id), api_key=raw_key)


@router.get("/agents/{agent_id}", response_model=AgentItem)
async def admin_agent_detail(
    agent_id: uuid.UUID,
    scope: Annotated[AdminScope, Depends(get_admin_scope)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> AgentItem:
    return await get_agent(db, scope, agent_id)


@router.post("/agents/{agent_id}/rotate-key", response_model=AgentKeyDisclosureResponse)
async def admin_rotate_agent_key(
    agent_id: uuid.UUID,
    scope: Annotated[AdminScope, Depends(get_admin_scope)],
    admin: Annotated[AdminUser, Depends(authenticate_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> AgentKeyDisclosureResponse:
    scope.require_superadmin()
    agent, raw_key = await rotate_agent_api_key(db, admin, agent_id)
    return AgentKeyDisclosureResponse(agent=await get_agent(db, scope, agent.id), api_key=raw_key)


@router.post("/agents/{agent_id}/revoke", response_model=AgentRevokeResponse)
async def admin_revoke_agent(
    agent_id: uuid.UUID,
    scope: Annotated[AdminScope, Depends(get_admin_scope)],
    admin: Annotated[AdminUser, Depends(authenticate_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> AgentRevokeResponse:
    scope.require_superadmin()
    agent, _changed = await revoke_agent_access(db, admin, agent_id)
    return AgentRevokeResponse(agent=await get_agent(db, scope, agent.id))


@router.post(
    "/agents/{agent_id}/full-resync", response_model=AgentCommandResponse, status_code=202
)
async def admin_request_full_resync(
    agent_id: uuid.UUID,
    scope: Annotated[AdminScope, Depends(get_admin_scope)],
    admin: Annotated[AdminUser, Depends(authenticate_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> AgentCommandResponse:
    scope.require_superadmin()
    command, _created = await request_full_resync(db, admin, agent_id)
    return AgentCommandResponse(
        command_id=command.id, status=cast(AgentCommandStatus, command.status)
    )


@router.get("/cards", response_model=Page[CardListItem])
async def admin_cards(
    scope: Annotated[AdminScope, Depends(get_admin_scope)],
    db: Annotated[AsyncSession, Depends(get_session)],
    page: Annotated[CardListPaginationParams, Depends()],
    business_id: uuid.UUID | None = None,
) -> Page[CardListItem]:
    return await list_cards(db, scope, business_id, page.limit, page.offset)


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


@router.post("/cards/{card_id}/unbind", response_model=CardUnbindResponse)
async def admin_unbind_card(
    card_id: uuid.UUID,
    scope: Annotated[AdminScope, Depends(get_admin_scope)],
    admin: Annotated[AdminUser, Depends(authenticate_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> CardUnbindResponse:
    result = await unbind_card(db, admin, scope, card_id)
    return CardUnbindResponse(status=cast(CardUnbindStatus, result))


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
    return await list_audit_logs(db, scope, page.limit, page.offset)


@router.get("/promotions", response_model=Page[PromotionAdminItem])
async def admin_promotions(
    scope: Annotated[AdminScope, Depends(get_admin_scope)],
    db: Annotated[AsyncSession, Depends(get_session)],
    page: Annotated[PaginationParams, Depends()],
    business_id: uuid.UUID | None = None,
) -> Page[PromotionAdminItem]:
    return await admin_content.list_promotions(db, scope, business_id, page.limit, page.offset)


@router.post("/promotions", response_model=PromotionAdminItem, status_code=201)
async def admin_create_promotion(
    body: PromotionCreateRequest,
    admin: Annotated[AdminUser, Depends(authenticate_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> PromotionAdminItem:
    return await admin_content.create_promotion(db, admin, body)


@router.patch("/promotions/{promotion_id}", response_model=PromotionAdminItem)
async def admin_update_promotion(
    promotion_id: uuid.UUID,
    body: PromotionUpdateRequest,
    admin: Annotated[AdminUser, Depends(authenticate_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[MediaStorage, Depends(get_media_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PromotionAdminItem:
    return await admin_content.update_promotion(
        db, admin, promotion_id, body, storage=storage, settings=settings
    )


@router.delete("/promotions/{promotion_id}", status_code=204)
async def admin_delete_promotion(
    promotion_id: uuid.UUID,
    admin: Annotated[AdminUser, Depends(authenticate_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[MediaStorage, Depends(get_media_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    await admin_content.delete_promotion(
        db, admin, promotion_id, storage=storage, settings=settings
    )
    return Response(status_code=204)


@router.get("/notifications", response_model=Page[NotificationAdminItem])
async def admin_notifications(
    scope: Annotated[AdminScope, Depends(get_admin_scope)],
    db: Annotated[AsyncSession, Depends(get_session)],
    page: Annotated[PaginationParams, Depends()],
    business_id: uuid.UUID | None = None,
) -> Page[NotificationAdminItem]:
    return await admin_content.list_notifications(db, scope, business_id, page.limit, page.offset)


@router.post("/notifications", response_model=NotificationAdminItem, status_code=201)
async def admin_create_notification(
    body: NotificationCreateRequest,
    admin: Annotated[AdminUser, Depends(authenticate_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> NotificationAdminItem:
    return await admin_content.create_notification(db, admin, body)


@router.delete("/notifications/{notification_id}", status_code=204)
async def admin_delete_notification(
    notification_id: uuid.UUID,
    admin: Annotated[AdminUser, Depends(authenticate_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    await admin_content.delete_notification(db, admin, notification_id)
    return Response(status_code=204)


@router.post("/media/images", response_model=ImageUploadResponse)
async def admin_upload_image(
    file: Annotated[UploadFile, File(...)],
    purpose: Annotated[str, Form(...)],
    admin: Annotated[AdminUser, Depends(authenticate_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[MediaStorage, Depends(get_media_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ImageUploadResponse:
    if purpose not in ("promotion", "logo"):
        raise AppError(
            "VALIDATION_ERROR",
            "purpose must be either 'promotion' or 'logo'.",
            status_code=422,
        )

    max_bytes = settings.media_max_upload_bytes
    total_bytes = 0
    chunks: list[bytes] = []
    chunk_size = 65536
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total_bytes += len(chunk)
        if total_bytes > max_bytes:
            raise AppError(
                "FILE_TOO_LARGE",
                f"File size exceeds maximum limit of {max_bytes} bytes.",
                status_code=413,
            )
        chunks.append(chunk)

    raw_bytes = b"".join(chunks)
    if not raw_bytes:
        raise AppError("VALIDATION_ERROR", "Uploaded file is empty.", status_code=422)

    return await process_and_store_image(
        raw_bytes=raw_bytes,
        purpose=purpose,
        settings=settings,
        storage=storage,
        admin=admin,
        db=db,
    )
