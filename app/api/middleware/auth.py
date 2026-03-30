from __future__ import annotations

import logging

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.security import _decode_token


logger = logging.getLogger("cypath_lite.middleware.auth")


class JWTAuthMiddleware(BaseHTTPMiddleware):
    """
    Optional middleware that decodes JWT when provided.

    Actual authorization is enforced via dependencies on each router/endpoint.
    """

    def __init__(self, app: ASGIApp, *, auto_decode: bool = True) -> None:
        super().__init__(app)
        self.auto_decode = auto_decode

    async def dispatch(self, request: Request, call_next):
        if self.auto_decode:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.lower().startswith("bearer "):
                token = auth_header.split(" ", 1)[1].strip()
                try:
                    request.state.jwt_payload = _decode_token(token)
                except Exception:
                    # Let endpoint dependencies decide whether the request is authenticated.
                    logger.debug("JWT decoding failed in middleware.")
        return await call_next(request)

