import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request, Response
from sqlalchemy import true
from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.sql.elements import ColumnElement

from app.core.admin_types import AdminRole
from app.core.errors import AppError
from app.models.admin import AdminUser
from app.services.admin_auth import authenticate_admin


@dataclass(frozen=True)
class AdminScope:
    admin_id: uuid.UUID
    role: AdminRole
    business_id: uuid.UUID | None

    def __post_init__(self) -> None:
        if not (
            (self.role == "superadmin" and self.business_id is None)
            or (self.role == "business_manager" and self.business_id is not None)
        ):
            raise AppError("ADMIN_UNAUTHENTICATED", "Admin authentication required", 401)

    def require_superadmin(self) -> None:
        if self.role != "superadmin":
            raise AppError("ADMIN_FORBIDDEN", "This operation is unavailable to your role", 403)

    def business_id_for(self, requested: uuid.UUID | None = None) -> uuid.UUID | None:
        if self.business_id is not None:
            if requested is not None and requested != self.business_id:
                raise AppError("ADMIN_RESOURCE_NOT_FOUND", "Resource not found", 404)
            return self.business_id
        self.require_superadmin()
        return requested

    def predicate(
        self,
        column: ColumnElement[uuid.UUID] | InstrumentedAttribute[uuid.UUID],
        requested: uuid.UUID | None = None,
    ) -> ColumnElement[bool]:
        business_id = self.business_id_for(requested)
        return column == business_id if business_id is not None else true()


def scope_for_admin(admin: AdminUser) -> AdminScope:
    if admin.role == "superadmin" and admin.business_id is None:
        return AdminScope(admin.id, "superadmin", None)
    if admin.role == "business_manager" and admin.business_id is not None:
        return AdminScope(admin.id, "business_manager", admin.business_id)
    raise AppError("ADMIN_UNAUTHENTICATED", "Admin authentication required", 401)


async def get_admin_scope(
    admin: Annotated[AdminUser, Depends(authenticate_admin)],
) -> AdminScope:
    return scope_for_admin(admin)


async def require_admin_origin(request: Request, response: Response) -> None:
    """One CSRF/transport dependency applies to every Admin API endpoint."""
    from app.core.config import settings
    from app.services.admin_security import require_admin_transport

    require_admin_transport(request)
    origin = request.headers.get("origin")
    if origin is None or origin not in settings.admin_allowed_origins:
        raise AppError("ADMIN_ORIGIN_FORBIDDEN", "Request origin is not allowed", 403)
    if request.headers.get("x-admin-request") != "1":
        raise AppError("ADMIN_CSRF_BLOCKED", "Admin request verification failed", 403)
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Pragma"] = "no-cache"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
