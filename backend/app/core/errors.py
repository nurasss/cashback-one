import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import get_current_request_id, get_safe_route_id


class AppError(Exception):
    """Base application exception for controlled API errors."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.extra = extra or {}
        super().__init__(message)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        error_content: dict[str, Any] = {"code": exc.code, "message": exc.message}
        if exc.extra:
            error_content.update(exc.extra)
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": error_content},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = "; ".join(
            f"{'.'.join(str(loc) for loc in err.get('loc', []))}: {err.get('msg')}"
            for err in exc.errors()
        )
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "VALIDATION_ERROR", "message": details}},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        req_id = getattr(request.state, "request_id", "") or get_current_request_id()
        safe_route = get_safe_route_id(request)
        is_prod = settings.app_env.lower() == "production"

        if is_prod:
            logging.getLogger("app.unhandled").error(
                "unhandled_request_exception",
                extra={
                    "event": "unhandled_request_exception",
                    "request_id": req_id,
                    "route": safe_route,
                    "exception_class": exc.__class__.__name__,
                    "status_code": 500,
                },
                exc_info=False,
            )
        else:
            logging.getLogger("app.unhandled").error(
                f"Unhandled exception during {request.method} {safe_route}: {exc.__class__.__name__}",
                exc_info=exc,
                extra={"request_id": req_id, "method": request.method, "route": safe_route},
            )
        headers = {"X-Request-ID": req_id} if req_id else {}
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_SERVER_ERROR", "message": "An internal server error occurred"}},
            headers=headers,
        )
