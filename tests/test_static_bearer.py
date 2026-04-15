from __future__ import annotations

import pytest
from starlette.datastructures import Headers

from api_billing_gateway import PlanTier
from api_billing_gateway.adapters import StaticBearerAdapter
from api_billing_gateway.context import AuthError


class FakeRequest:
    def __init__(self, headers: dict[str, str]):
        self.headers = Headers(headers)


def test_matches_bearer_header():
    a = StaticBearerAdapter(api_key="key1")
    assert a.matches(FakeRequest({"Authorization": "Bearer abc"}))
    assert a.matches(FakeRequest({"authorization": "bearer abc"}))
    assert not a.matches(FakeRequest({"X-RapidAPI-Proxy-Secret": "x"}))


def test_authenticate_success():
    a = StaticBearerAdapter(api_key="sekret", default_tier=PlanTier.PRO)
    ctx = a.authenticate(FakeRequest({"Authorization": "Bearer sekret"}))
    assert ctx.tier == PlanTier.PRO
    assert ctx.source == "bearer"
    assert ctx.external_user_id.startswith("bearer:")


def test_authenticate_rejects_wrong_token():
    a = StaticBearerAdapter(api_key="sekret")
    with pytest.raises(AuthError) as ei:
        a.authenticate(FakeRequest({"Authorization": "Bearer nope"}))
    assert ei.value.status_code == 401


def test_authenticate_rejects_empty_token():
    a = StaticBearerAdapter(api_key="sekret")
    with pytest.raises(AuthError):
        a.authenticate(FakeRequest({"Authorization": "Bearer "}))


def test_ctor_rejects_empty_key():
    with pytest.raises(ValueError):
        StaticBearerAdapter(api_key="")
