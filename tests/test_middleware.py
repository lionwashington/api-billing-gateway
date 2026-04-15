from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from api_billing_gateway import BillingMiddleware, PlanTier
from api_billing_gateway.adapters import ProxySecretAdapter, StaticBearerAdapter


TIER_MAP = {
    "BASIC": PlanTier.FREE,
    "PRO": PlanTier.STARTER,
    "ULTRA": PlanTier.PRO,
    "MEGA": PlanTier.BUSINESS,
}


def build_app(*, auth_enabled: bool = True) -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        BillingMiddleware,
        adapters=[
            ProxySecretAdapter(
                name="rapidapi",
                secret_value="proxy123",
                secret_header="X-RapidAPI-Proxy-Secret",
                user_header="X-RapidAPI-User",
                tier_header="X-RapidAPI-Subscription",
                tier_map=TIER_MAP,
            ),
            StaticBearerAdapter(api_key="bearer123", default_tier=PlanTier.PRO),
        ],
        auth_enabled=auth_enabled,
    )

    @app.get("/api/echo")
    async def echo(request: Request):
        b = request.state.billing
        return {
            "source": b.source,
            "tier": b.tier.value,
            "mode": b.mode,
            "user": b.external_user_id,
        }

    @app.get("/health")
    async def health():
        return {"ok": True}

    return app


def test_exempt_path_passes_without_auth():
    client = TestClient(build_app())
    r = client.get("/health")
    assert r.status_code == 200


def test_no_auth_on_protected_returns_401():
    client = TestClient(build_app())
    r = client.get("/api/echo")
    assert r.status_code == 401


def test_proxy_secret_routes_tier():
    client = TestClient(build_app())
    r = client.get(
        "/api/echo",
        headers={
            "X-RapidAPI-Proxy-Secret": "proxy123",
            "X-RapidAPI-Subscription": "MEGA",
            "X-RapidAPI-User": "u1",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "rapidapi"
    assert body["tier"] == "business"
    assert body["user"] == "u1"


def test_proxy_secret_wrong_value_rejected():
    client = TestClient(build_app())
    r = client.get(
        "/api/echo",
        headers={"X-RapidAPI-Proxy-Secret": "wrong"},
    )
    assert r.status_code == 403


def test_bearer_fallback():
    client = TestClient(build_app())
    r = client.get("/api/echo", headers={"Authorization": "Bearer bearer123"})
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "bearer"
    assert body["tier"] == "pro"


def test_auth_disabled_injects_test_context():
    client = TestClient(build_app(auth_enabled=False))
    r = client.get("/api/echo")
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "disabled-test"
    assert body["tier"] == "free"
