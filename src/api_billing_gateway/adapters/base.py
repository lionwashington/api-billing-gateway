from __future__ import annotations

from typing import Protocol, runtime_checkable

from starlette.requests import Request

from ..context import AuthContext


@runtime_checkable
class BillingAdapter(Protocol):
    name: str

    def matches(self, request: Request) -> bool: ...

    def authenticate(self, request: Request) -> AuthContext | None: ...

    async def report_usage(self, ctx: AuthContext, units: int = 1) -> None: ...
