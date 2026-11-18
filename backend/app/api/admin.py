import uuid
from datetime import datetime
from typing import Annotated, cast

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin_deps import (
    AdminScope,
    get_admin_scope,
    require_admin_origin,
    scope_for_admin,
)
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.db.session import get_session
from app.models.admin import AdminUser
from app.models.entities import AuditLog, BusinessSplashAsset
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
    CardListPaginationParams,
    CardPage,
    CardSearchRequest,
    CardUnbindResponse,
    CardUnbindStatus,
    DashboardResponse,
    ManagerAccessDisclosure,
    Page,
    PaginationParams,
    PosKeyCreateRequest,
    PosKeyCreateResponse,
    PosKeyItem,
    TransactionPage,
    UserDetail,
    UserListItem,
    UserSearchRequest,
)
from app.schemas.admin_content import (
    AppTextsResponse,
    AppTextsUpdateRequest,
    BusinessLoyaltyTierAdminItem,
    BusinessLoyaltyTierCreateRequest,
    BusinessLoyaltyTierUpdateRequest,
    BusinessSplashConfigResponse,
    BusinessSplashConfigUpdateRequest,
    BusinessStoreAdminItem,
    BusinessStoreCreateRequest,
    BusinessStoreUpdateRequest,
    ImageUploadResponse,
    LoyaltyScaleResponse,
    LoyaltyScaleSaveRequest,
    LoyaltyScaleSaveResponse,
    NotificationAdminItem,
    NotificationCreateRequest,
    PromotionAdminItem,
    PromotionCreateRequest,
    PromotionKind,
    PromotionUpdateRequest,
    SplashMediaUploadResponse,
    StoreResolveCoordinatesRequest,
    StoreResolveCoordinatesResponse,
)
from app.services import admin_content
from app.services.admin_auth import authenticate_admin
from app.services.admin_mutations import (
    create_agent,
    create_business,
    create_pos_key_mutation,
    request_full_resync,
    reset_or_create_business_manager,
    revoke_agent_access,
    revoke_pos_key_mutation,
    rotate_agent_api_key,
    safe_audit_snapshot,
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
    list_card_transactions,
    list_cards,
    list_pos_keys,
    list_user_transactions,
    list_users,
    search_cards,
    search_users,
)
from app.services.geo_service import resolve_store_coordinates
from app.services.image_service import process_and_store_image
from app.services.media_storage import MediaStorage, get_media_storage
from app.services.push_sender import PushSender, get_push_sender
from app.services.video_service import validate_mp4_video

router = APIRouter(dependencies=[Depends(require_admin_origin)])


@router.get("/me", response_model=AdminMeResponse)
async def admin_me(
    admin: Annotated[AdminUser, Depends(authenticate_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AdminMeResponse:
    return AdminMeResponse(
        admin=AdminIdentity.model_validate(await admin_identity(db, admin)),
        admin_stats_unlimited_period=True,
        admin_max_stats_period_days=settings.admin_max_stats_period_days,
    )


@router.get("/dashboard", response_model=DashboardResponse)
async def admin_dashboard(
    scope: Annotated[AdminScope, Depends(get_admin_scope)],
    db: Annotated[AsyncSession, Depends(get_session)],
    business_id: uuid.UUID | None = None,
    start: Annotated[datetime | None, Query(alias="from")] = None,
    end: Annotated[datetime | None, Query(alias="to")] = None,
) -> DashboardResponse:
    if start is not None and not (1000 <= start.year <= 9999):
        raise AppError(
            "ADMIN_INVALID_PERIOD", "Start year must be 4 digits", 422, extra={"reason": "PERIOD_YEAR_INVALID"}
        )
    if end is not None and not (1000 <= end.year <= 9999):
        raise AppError(
            "ADMIN_INVALID_PERIOD", "End year must be 4 digits", 422, extra={"reason": "PERIOD_YEAR_INVALID"}
        )
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
    scope.business_id_for(business_id)
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


@router.get(
    "/businesses/{business_id}/stores", response_model=list[BusinessStoreAdminItem]
)
async def admin_list_stores(
    business_id: uuid.UUID,
    admin: Annotated[AdminUser, Depends(authenticate_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> list[BusinessStoreAdminItem]:
    return await admin_content.list_stores(db, admin, business_id)


@router.post(
    "/businesses/{business_id}/stores",
    response_model=BusinessStoreAdminItem,
    status_code=201,
)
async def admin_create_store(
    business_id: uuid.UUID,
    body: BusinessStoreCreateRequest,
    admin: Annotated[AdminUser, Depends(authenticate_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> BusinessStoreAdminItem:
    return await admin_content.create_store(db, admin, business_id, body)


@router.patch(
    "/businesses/{business_id}/stores/{store_id}",
    response_model=BusinessStoreAdminItem,
)
async def admin_update_store(
    business_id: uuid.UUID,
    store_id: uuid.UUID,
    body: BusinessStoreUpdateRequest,
    admin: Annotated[AdminUser, Depends(authenticate_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> BusinessStoreAdminItem:
    return await admin_content.update_store(db, admin, business_id, store_id, body)


@router.delete("/businesses/{business_id}/stores/{store_id}", status_code=204)
async def admin_delete_store(
    business_id: uuid.UUID,
    store_id: uuid.UUID,
    admin: Annotated[AdminUser, Depends(authenticate_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    await admin_content.delete_store(db, admin, business_id, store_id)
    return Response(status_code=204)


@router.post(
    "/businesses/{business_id}/stores/resolve-coordinates",
    response_model=StoreResolveCoordinatesResponse,
)
async def admin_resolve_store_coordinates(
    business_id: uuid.UUID,
    body: StoreResolveCoordinatesRequest,
    admin: Annotated[AdminUser, Depends(authenticate_admin)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> StoreResolveCoordinatesResponse:
    scope = scope_for_admin(admin)
    admin_content._check_business_scope(scope, business_id)
    return await resolve_store_coordinates(
        query=body.query,
        url=body.url,
        address=body.address,
        settings=settings,
    )


@router.get(
    "/businesses/{business_id}/loyalty-tiers",
    response_model=list[BusinessLoyaltyTierAdminItem],
)
async def admin_list_loyalty_tiers(
    business_id: uuid.UUID,
    admin: Annotated[AdminUser, Depends(authenticate_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> list[BusinessLoyaltyTierAdminItem]:
    return await admin_content.list_loyalty_tiers(db, admin, business_id)


@router.get(
    "/businesses/{business_id}/loyalty-tiers/scale",
    response_model=LoyaltyScaleResponse,
)
async def admin_get_loyalty_scale(
    business_id: uuid.UUID,
    admin: Annotated[AdminUser, Depends(authenticate_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> LoyaltyScaleResponse:
    return await admin_content.get_loyalty_scale(db, admin, business_id)


@router.put(
    "/businesses/{business_id}/loyalty-tiers/scale",
    response_model=LoyaltyScaleSaveResponse,
)
async def admin_save_loyalty_scale(
    business_id: uuid.UUID,
    body: LoyaltyScaleSaveRequest,
    admin: Annotated[AdminUser, Depends(authenticate_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LoyaltyScaleSaveResponse:
    return await admin_content.save_loyalty_scale(db, admin, business_id, body, settings=settings)


@router.post(
    "/businesses/{business_id}/loyalty-tiers",
    response_model=BusinessLoyaltyTierAdminItem,
    status_code=201,
)
async def admin_create_loyalty_tier(
    business_id: uuid.UUID,
    body: BusinessLoyaltyTierCreateRequest,
    admin: Annotated[AdminUser, Depends(authenticate_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> BusinessLoyaltyTierAdminItem:
    return await admin_content.create_loyalty_tier(db, admin, business_id, body, settings=settings)


@router.patch(
    "/businesses/{business_id}/loyalty-tiers/{tier_id}",
    response_model=BusinessLoyaltyTierAdminItem,
)
async def admin_update_loyalty_tier(
    business_id: uuid.UUID,
    tier_id: uuid.UUID,
    body: BusinessLoyaltyTierUpdateRequest,
    admin: Annotated[AdminUser, Depends(authenticate_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> BusinessLoyaltyTierAdminItem:
    return await admin_content.update_loyalty_tier(
        db, admin, business_id, tier_id, body, settings=settings
    )


@router.delete("/businesses/{business_id}/loyalty-tiers/{tier_id}", status_code=204)
async def admin_delete_loyalty_tier(
    business_id: uuid.UUID,
    tier_id: uuid.UUID,
    admin: Annotated[AdminUser, Depends(authenticate_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    await admin_content.delete_loyalty_tier(db, admin, business_id, tier_id)
    return Response(status_code=204)


@router.get("/businesses/{business_id}/app-texts", response_model=AppTextsResponse)
async def admin_get_app_texts(
    business_id: uuid.UUID,
    admin: Annotated[AdminUser, Depends(authenticate_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> AppTextsResponse:
    return await admin_content.get_app_texts(db, admin, business_id)


@router.put("/businesses/{business_id}/app-texts", response_model=AppTextsResponse)
async def admin_update_app_texts(
    business_id: uuid.UUID,
    body: AppTextsUpdateRequest,
    admin: Annotated[AdminUser, Depends(authenticate_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> AppTextsResponse:
    return await admin_content.update_app_texts(db, admin, business_id, body)



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


@router.get("/businesses/{business_id}/pos-keys", response_model=list[PosKeyItem])
async def admin_get_pos_keys(
    business_id: uuid.UUID,
    scope: Annotated[AdminScope, Depends(get_admin_scope)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> list[PosKeyItem]:
    keys = await list_pos_keys(db, scope, business_id)
    return [PosKeyItem.model_validate(k) for k in keys]


@router.post(
    "/businesses/{business_id}/pos-keys",
    response_model=PosKeyCreateResponse,
    status_code=201,
)
async def admin_create_pos_key(
    business_id: uuid.UUID,
    body: PosKeyCreateRequest,
    admin: Annotated[AdminUser, Depends(authenticate_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> PosKeyCreateResponse:
    pos_key, raw_key = await create_pos_key_mutation(db, admin, business_id, body.name)
    return PosKeyCreateResponse(pos_key=PosKeyItem.model_validate(pos_key), api_key=raw_key)


@router.post("/pos-keys/{key_id}/revoke", response_model=PosKeyItem)
async def admin_revoke_pos_key(
    key_id: uuid.UUID,
    admin: Annotated[AdminUser, Depends(authenticate_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> PosKeyItem:
    pos_key = await revoke_pos_key_mutation(db, admin, key_id)
    return PosKeyItem.model_validate(pos_key)


@router.get("/cards", response_model=CardPage)
async def admin_cards(
    scope: Annotated[AdminScope, Depends(get_admin_scope)],
    db: Annotated[AsyncSession, Depends(get_session)],
    page: Annotated[CardListPaginationParams, Depends()],
    business_id: uuid.UUID | None = None,
) -> CardPage:
    return await list_cards(db, scope, business_id, page.limit, page.offset)


@router.post("/cards/search", response_model=CardPage)
async def admin_search_cards(
    body: CardSearchRequest,
    scope: Annotated[AdminScope, Depends(get_admin_scope)],
    db: Annotated[AsyncSession, Depends(get_session)],
    page: Annotated[PaginationParams, Depends()],
) -> CardPage:
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


@router.get("/cards/{card_id}/transactions", response_model=TransactionPage)
async def admin_card_transactions(
    card_id: uuid.UUID,
    scope: Annotated[AdminScope, Depends(get_admin_scope)],
    db: Annotated[AsyncSession, Depends(get_session)],
    page: Annotated[PaginationParams, Depends()],
) -> TransactionPage:
    return await list_card_transactions(db, scope, card_id, page.limit, page.offset)


@router.post("/cards/{card_id}/unbind", response_model=CardUnbindResponse)
async def admin_unbind_card(
    card_id: uuid.UUID,
    scope: Annotated[AdminScope, Depends(get_admin_scope)],
    admin: Annotated[AdminUser, Depends(authenticate_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> CardUnbindResponse:
    result = await unbind_card(db, admin, scope, card_id)
    return CardUnbindResponse(status=cast(CardUnbindStatus, result))


@router.get("/users", response_model=Page[UserListItem])
async def admin_list_users(
    scope: Annotated[AdminScope, Depends(get_admin_scope)],
    db: Annotated[AsyncSession, Depends(get_session)],
    page: Annotated[PaginationParams, Depends()],
    business_id: uuid.UUID | None = None,
) -> Page[UserListItem]:
    return await list_users(db, scope, business_id, page.limit, page.offset)


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


@router.get("/users/{user_id}/transactions", response_model=TransactionPage)
async def admin_user_transactions(
    user_id: uuid.UUID,
    scope: Annotated[AdminScope, Depends(get_admin_scope)],
    db: Annotated[AsyncSession, Depends(get_session)],
    page: Annotated[PaginationParams, Depends()],
    business_id: uuid.UUID | None = None,
) -> TransactionPage:
    return await list_user_transactions(db, scope, user_id, business_id, page.limit, page.offset)


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
    kind: PromotionKind | None = None,
) -> Page[PromotionAdminItem]:
    return await admin_content.list_promotions(
        db, scope, business_id, page.limit, page.offset, kind=kind
    )


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
    sender: Annotated[PushSender, Depends(get_push_sender)],
) -> NotificationAdminItem:
    return await admin_content.create_notification(db, admin, body, sender=sender)


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
    business_id: Annotated[uuid.UUID | None, Form()] = None,
) -> ImageUploadResponse:
    if purpose not in ("promotion", "logo"):
        raise AppError(
            "VALIDATION_ERROR",
            "purpose must be either 'promotion' or 'logo'.",
            status_code=422,
        )

    if admin.role == "business_manager":
        if business_id is not None and business_id != admin.business_id:
            raise AppError("FORBIDDEN", "Cannot upload media for another business", status_code=403)
        target_business_id = admin.business_id
    else:
        target_business_id = business_id or admin.business_id

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

    res = await process_and_store_image(
        raw_bytes=raw_bytes,
        purpose=purpose,
        settings=settings,
        storage=storage,
        admin=admin,
        db=db,
    )
    asset = BusinessSplashAsset(
        business_id=target_business_id,
        media_type="image",
        media_url=res.url,
        width=res.width,
        height=res.height,
        duration_seconds=None,
        file_size=res.bytes,
    )
    db.add(asset)
    await db.commit()
    return res


MAX_SPLASH_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MiB limit for splash assets (video)


@router.post("/media/splash", response_model=SplashMediaUploadResponse)
async def admin_upload_splash_media(
    file: Annotated[UploadFile, File(...)],
    admin: Annotated[AdminUser, Depends(authenticate_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[MediaStorage, Depends(get_media_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
    business_id: Annotated[uuid.UUID | None, Form()] = None,
) -> SplashMediaUploadResponse:
    # 1. Scope check
    if admin.role == "business_manager":
        if business_id is not None and business_id != admin.business_id:
            raise AppError("FORBIDDEN", "Cannot upload splash for another business", status_code=403)
        target_business_id = admin.business_id
    else:
        target_business_id = business_id or admin.business_id

    # 2. Read in chunks up to 15 MiB
    max_bytes = MAX_SPLASH_UPLOAD_BYTES
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
                f"File size exceeds maximum splash limit of {max_bytes} bytes (15 MiB).",
                status_code=413,
            )
        chunks.append(chunk)

    raw_bytes = b"".join(chunks)
    if not raw_bytes:
        raise AppError("VALIDATION_ERROR", "Uploaded file is empty.", status_code=422)

    # 3. Detect format: MP4 video or Image
    content_type = (file.content_type or "").lower()
    filename = (file.filename or "").lower()
    is_mp4_box = len(raw_bytes) >= 8 and (raw_bytes[4:8] == b"ftyp" or b"ftyp" in raw_bytes[:64])
    is_video_hint = content_type.startswith("video/") or filename.endswith(
        (".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm")
    )

    if is_mp4_box or is_video_hint:
        # Validate MP4 video (H.264, duration <= 5.0, no audio)
        meta = validate_mp4_video(raw_bytes)
        file_id = uuid.uuid4().hex
        relative_path = f"splashes/{file_id}.mp4"
        await storage.put(relative_path, raw_bytes)
        public_url = f"{settings.media_public_base_url.rstrip('/')}/{relative_path}"
        media_type = "video"
        width = meta.width
        height = meta.height
        duration_seconds = meta.duration_seconds
    else:
        # Image: limit to 5 MiB
        if len(raw_bytes) > 5 * 1024 * 1024:
            raise AppError(
                "IMAGE_TOO_LARGE",
                "Размер изображения заставки не должен превышать 5 МБ.",
                status_code=413,
            )
        img_res = await process_and_store_image(
            raw_bytes=raw_bytes,
            purpose="splash",
            settings=settings,
            storage=storage,
            admin=admin,
            db=db,
        )
        public_url = img_res.url
        media_type = "image"
        width = img_res.width
        height = img_res.height
        duration_seconds = None

    asset = BusinessSplashAsset(
        business_id=target_business_id,
        media_type=media_type,
        media_url=public_url,
        width=width,
        height=height,
        duration_seconds=duration_seconds,
        file_size=len(raw_bytes),
    )
    db.add(asset)

    if target_business_id is not None:
        db.add(
            AuditLog(
                actor=admin.login,
                admin_user_id=admin.id,
                business_id=target_business_id,
                action="media_uploaded",
                entity="splash_media",
                before_state=None,
                after_state=safe_audit_snapshot(
                    "media_uploaded",
                    {
                        "purpose": "splash",
                        "media_type": media_type,
                        "bytes": len(raw_bytes),
                        "width": width,
                        "height": height,
                        "duration_seconds": duration_seconds,
                        "url": public_url,
                    },
                    admin_user_id=admin.id,
                    business_id=target_business_id,
                ),
            )
        )
    await db.commit()

    return SplashMediaUploadResponse(
        url=public_url,
        media_type=media_type,
        width=width,
        height=height,
        duration_seconds=duration_seconds,
        bytes=len(raw_bytes),
    )


@router.get(
    "/businesses/{business_id}/splash",
    response_model=BusinessSplashConfigResponse,
)
async def admin_get_business_splash(
    business_id: uuid.UUID,
    admin: Annotated[AdminUser, Depends(authenticate_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> BusinessSplashConfigResponse:
    return await admin_content.get_splash_config(db, admin, business_id)


@router.put(
    "/businesses/{business_id}/splash",
    response_model=BusinessSplashConfigResponse,
)
async def admin_update_business_splash(
    business_id: uuid.UUID,
    body: BusinessSplashConfigUpdateRequest,
    admin: Annotated[AdminUser, Depends(authenticate_admin)],
    db: Annotated[AsyncSession, Depends(get_session)],
    storage: Annotated[MediaStorage, Depends(get_media_storage)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> BusinessSplashConfigResponse:
    return await admin_content.update_splash_config(
        db, admin, business_id, body, storage=storage, settings=settings
    )
