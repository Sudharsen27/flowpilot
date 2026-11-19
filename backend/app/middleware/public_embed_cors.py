"""CORS for public embed routes based on per-organization allowed origins."""

from __future__ import annotations

import re
from collections.abc import MutableMapping
from typing import Any

from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.embed_origins import origin_is_allowed
from app.db.session import SessionLocal
from app.repositories.organization_repository import OrganizationRepository

_PUBLIC_ORG_PATH = re.compile(
    r"^/api/v1/public/organizations/([^/]+)/(?:enquiries|chat-enquiries)/?$"
)

# Overridable in tests so CORS lookups use the same SQLite session factory.
session_factory = SessionLocal


class PublicEmbedCorsMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path") or ""
        match = _PUBLIC_ORG_PATH.match(path)
        if match is None:
            await self.app(scope, receive, send)
            return

        headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in scope.get("headers", [])
        }
        origin = headers.get("origin")
        slug = match.group(1)
        allowed = self._origin_allowed(slug, origin)

        # Only take over CORS for allowlisted embed origins. Otherwise fall
        # through so global CORS (e.g. localhost:3000 hosted form) can apply.
        if not allowed:
            await self.app(scope, receive, send)
            return

        if scope.get("method") == "OPTIONS":
            response = Response(status_code=204)
            if origin:
                self._apply_cors(response, origin)
            await response(scope, receive, send)
            return

        async def send_with_cors(message: MutableMapping[str, Any]) -> None:
            if origin and message["type"] == "http.response.start":
                raw_headers = list(message.get("headers") or [])
                extra = [
                    (b"access-control-allow-origin", origin.encode("latin-1")),
                    (b"access-control-allow-methods", b"GET, POST, OPTIONS"),
                    (
                        b"access-control-allow-headers",
                        b"Content-Type, Accept",
                    ),
                    (b"vary", b"Origin"),
                ]
                message = {**message, "headers": raw_headers + extra}
            await send(message)

        await self.app(scope, receive, send_with_cors)

    def _origin_allowed(self, slug: str, origin: str | None) -> bool:
        session = session_factory()
        try:
            organization = OrganizationRepository(session).get_by_slug(slug)
            if organization is None:
                return False
            return origin_is_allowed(organization.website_embed_allowed_origins, origin)
        finally:
            session.close()

    @staticmethod
    def _apply_cors(response: Response, origin: str) -> None:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Accept"
        response.headers["Vary"] = "Origin"
