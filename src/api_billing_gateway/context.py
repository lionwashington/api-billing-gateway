from __future__ import annotations

from dataclasses import dataclass

from .tier import PlanTier


@dataclass(frozen=True)
class AuthContext:
    source: str
    external_user_id: str
    tier: PlanTier
    raw_tier: str = ""
    mode: str = "authed"  # "authed" | "disabled-test"


class AuthError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
