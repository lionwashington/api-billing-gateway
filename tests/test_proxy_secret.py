from __future__ import annotations

import pytest
from starlette.datastructures import Headers

from api_billing_gateway import PlanTier
from api_billing_gateway.adapters import ProxySecretAdapter
from api_billing_gateway.context import AuthError


class FakeRequest:
    def __init__(self, headers: dict[str, str]):
        self.headers = Headers(headers)


RAPIDAPI_TIER_MAP = {
    "BASIC": PlanTier.FREE,
    "PRO": PlanTier.STARTER,
    "ULTRA": PlanTier.PRO,
    "MEGA": PlanTier.BUSINESS,
}


def make_adapter(secret: str = "s3cret") -> ProxySecretAdapter:
    return ProxySecretAdapter(
        name="rapidapi",
        secret_value=secret,
        secret_header="X-RapidAPI-Proxy-Secret",
        user_header="X-RapidAPI-User",
        tier_header="X-RapidAPI-Subscription",
        tier_map=RAPIDAPI_TIER_MAP,
    )


def test_matches_by_secret_header_present():
    a = make_adapter()
    assert a.matches(FakeRequest({"X-RapidAPI-Proxy-Secret": "whatever"}))
    assert not a.matches(FakeRequest({"Authorization": "Bearer x"}))


def test_authenticate_rejects_wrong_secret():
    a = make_adapter(secret="correct")
    with pytest.raises(AuthError) as ei:
        a.authenticate(FakeRequest({"X-RapidAPI-Proxy-Secret": "wrong"}))
    assert ei.value.status_code == 403


@pytest.mark.parametrize("raw,expected", [
    ("BASIC", PlanTier.FREE),
    ("PRO", PlanTier.STARTER),
    ("ULTRA", PlanTier.PRO),
    ("MEGA", PlanTier.BUSINESS),
    ("basic", PlanTier.FREE),
    ("  PRO  ", PlanTier.STARTER),
    ("UNKNOWN", PlanTier.FREE),
    ("", PlanTier.FREE),
])
def test_authenticate_tier_mapping(raw, expected):
    a = make_adapter()
    ctx = a.authenticate(FakeRequest({
        "X-RapidAPI-Proxy-Secret": "s3cret",
        "X-RapidAPI-Subscription": raw,
        "X-RapidAPI-User": "alice",
    }))
    assert ctx.tier == expected
    assert ctx.raw_tier == raw.strip()
    assert ctx.external_user_id == "alice"
    assert ctx.source == "rapidapi"
    assert ctx.mode == "authed"


def test_missing_subscription_defaults_to_free():
    a = make_adapter()
    ctx = a.authenticate(FakeRequest({"X-RapidAPI-Proxy-Secret": "s3cret"}))
    assert ctx.tier == PlanTier.FREE
    assert ctx.external_user_id == "anonymous"


def test_ctor_rejects_empty_secret():
    with pytest.raises(ValueError):
        ProxySecretAdapter(
            name="x", secret_value="",
            secret_header="H", user_header="U", tier_header="T",
            tier_map={},
        )
