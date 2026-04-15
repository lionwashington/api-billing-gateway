from __future__ import annotations

from typing import Mapping

from starlette.requests import Request

from ..context import AuthContext, AuthError
from ..tier import PlanTier


class ProxySecretAdapter:
    """
    Marketplace-agnostic adapter for the "gateway injects a shared secret + user id + tier" pattern.

    Covers RapidAPI, Zyla, APYHub, Postman and any clone with the same header shape — switch by config.
    """

    def __init__(
        self,
        *,
        name: str,
        secret_value: str,
        secret_header: str,
        user_header: str,
        tier_header: str,
        tier_map: Mapping[str, PlanTier],
        default_tier: PlanTier = PlanTier.FREE,
    ) -> None:
        if not secret_value:
            raise ValueError(f"{name}: secret_value is required")
        self.name = name
        self._secret_value = secret_value
        self._secret_header = secret_header
        self._user_header = user_header
        self._tier_header = tier_header
        self._tier_map = {k.strip().upper(): v for k, v in tier_map.items()}
        self._default_tier = default_tier

    def matches(self, request: Request) -> bool:
        return self._secret_header in request.headers

    def authenticate(self, request: Request) -> AuthContext:
        sent = request.headers.get(self._secret_header, "")
        if sent != self._secret_value:
            raise AuthError(403, f"{self.name}: invalid proxy secret")

        raw_tier = (request.headers.get(self._tier_header) or "").strip()
        tier = self._tier_map.get(raw_tier.upper(), self._default_tier)
        user_id = request.headers.get(self._user_header) or "anonymous"

        return AuthContext(
            source=self.name,
            external_user_id=user_id,
            tier=tier,
            raw_tier=raw_tier,
            mode="authed",
        )

    async def report_usage(self, ctx: AuthContext, units: int = 1) -> None:
        # Marketplace meters usage on its side; nothing to do here.
        return
