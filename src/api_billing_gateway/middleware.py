from __future__ import annotations

from typing import Iterable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from .adapters.base import BillingAdapter
from .context import AuthContext, AuthError
from .tier import PlanTier

DEFAULT_EXEMPT_PATHS = frozenset({"/health", "/docs", "/openapi.json", "/redoc"})


class BillingMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        *,
        adapters: Iterable[BillingAdapter],
        auth_enabled: bool = True,
        exempt_paths: Iterable[str] = DEFAULT_EXEMPT_PATHS,
        protected_prefix: str = "/api/",
    ) -> None:
        super().__init__(app)
        self._adapters = list(adapters)
        self._auth_enabled = auth_enabled
        self._exempt = frozenset(exempt_paths)
        self._protected_prefix = protected_prefix

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if not self._auth_enabled:
            request.state.billing = AuthContext(
                source="disabled",
                external_user_id="dev",
                tier=PlanTier.FREE,
                raw_tier="",
                mode="disabled-test",
            )
            return await call_next(request)

        if path in self._exempt or not path.startswith(self._protected_prefix):
            return await call_next(request)

        for adapter in self._adapters:
            if not adapter.matches(request):
                continue
            try:
                ctx = adapter.authenticate(request)
            except AuthError as e:
                return JSONResponse({"detail": e.detail}, status_code=e.status_code)
            request.state.billing = ctx
            return await call_next(request)

        return JSONResponse(
            {"detail": "authentication required"},
            status_code=401,
        )
