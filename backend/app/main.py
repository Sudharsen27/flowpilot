import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.api.health import router as health_router
from app.api.v1 import api_router
from app.core.config import settings
from app.core.exceptions import AppError

logger = logging.getLogger(__name__)


class UnhandledErrorMiddleware:
    """Turn unexpected failures into a response before they leave the CORS layer.

    FastAPI handles a bare ``Exception`` handler in ``ServerErrorMiddleware``, which
    sits outside CORS. The browser then reports the 500 as a missing
    ``Access-Control-Allow-Origin`` header.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        try:
            await self.app(scope, receive, send)
        except Exception:
            logger.exception("Unhandled API error")
            response = JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
            )
            await response(scope, receive, send)


def create_app() -> FastAPI:
    application = FastAPI(title=settings.app_name, version="0.1.0")
    # Added before CORS so CORS stays outside and can tag this response.
    application.add_middleware(UnhandledErrorMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_origin_regex=settings.cors_allow_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(health_router)
    application.include_router(api_router)

    @application.exception_handler(AppError)
    async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
        return JSONResponse(
            status_code=exc.status_code,
            content=exc.content,
            headers=headers,
        )

    return application


app = create_app()
