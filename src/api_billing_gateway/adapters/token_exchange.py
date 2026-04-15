from __future__ import annotations

from starlette.requests import Request

from ..context import AuthContext


class TokenExchangeAdapter:
    """
    Skeleton for OAuth / marketplace-issued short token flows (AWS Marketplace, Google API Gateway).

    Planned for v0.2+. v0.1 never matches and raises on authenticate.
    """

    name = "token-exchange"

    def matches(self, request: Request) -> bool:
        return False

    def authenticate(self, request: Request) -> AuthContext:
        raise NotImplementedError("TokenExchangeAdapter planned for v0.2+")

    async def report_usage(self, ctx: AuthContext, units: int = 1) -> None:
        raise NotImplementedError("TokenExchangeAdapter planned for v0.2+")
