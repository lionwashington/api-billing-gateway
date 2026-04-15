from __future__ import annotations

import hashlib
from typing import Mapping, Optional

from starlette.requests import Request

from ..context import AuthContext, AuthError
from ..tier import PlanTier


class StaticBearerAdapter:
    """
    Direct `Authorization: Bearer <api_key>` adapter for self-operated access.

    Useful for ops/monitoring/internal calls that skip a marketplace entirely.

    Optional tier_header + tier_map lets ops override tier per request
    (e.g. to reuse the same subscription header shape as marketplace adapters).
    """

    def __init__(
        self,
        *,
        name: str = "bearer",
        api_key: str,
        default_tier: PlanTier = PlanTier.PRO,
        tier_header: Optional[str] = None,
        tier_map: Optional[Mapping[str, PlanTier]] = None,
    ) -> None:
        if not api_key:
            raise ValueError(f"{name}: api_key is required")
        self.name = name
        self._api_key = api_key
        self._default_tier = default_tier
        self._tier_header = tier_header
        self._tier_map = (
            {k.strip().upper(): v for k, v in tier_map.items()} if tier_map else None
        )

    def matches(self, request: Request) -> bool:
        auth = request.headers.get("authorization", "")
        return auth.lower().startswith("bearer ")

    def authenticate(self, request: Request) -> AuthContext:
        auth = request.headers.get("authorization", "")
        token = auth[7:].strip() if len(auth) > 7 else ""
        if not token or token != self._api_key:
            raise AuthError(401, f"{self.name}: invalid bearer token")

        user_id = "bearer:" + hashlib.sha256(token.encode()).hexdigest()[:12]

        tier = self._default_tier
        raw_tier = self._default_tier.value
        if self._tier_header and self._tier_map:
            raw = (request.headers.get(self._tier_header) or "").strip()
            if raw:
                raw_tier = raw
                tier = self._tier_map.get(raw.upper(), self._default_tier)

        return AuthContext(
            source=self.name,
            external_user_id=user_id,
            tier=tier,
            raw_tier=raw_tier,
            mode="authed",
        )

    async def report_usage(self, ctx: AuthContext, units: int = 1) -> None:
        return
