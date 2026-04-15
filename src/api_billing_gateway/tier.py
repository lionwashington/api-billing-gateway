from __future__ import annotations

from enum import Enum


class PlanTier(str, Enum):
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    BUSINESS = "business"

    @classmethod
    def safe(cls, value: str | None, default: "PlanTier" = None) -> "PlanTier":
        if value is None:
            return default or cls.FREE
        try:
            return cls(value.strip().lower())
        except (ValueError, AttributeError):
            return default or cls.FREE
