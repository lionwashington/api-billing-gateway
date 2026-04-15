# api-billing-gateway (abg)

> **No credential storage by design** — adapters receive secrets from the caller and keep them only in instance state for the lifetime of the process. See [`docs/SECURITY_AUDIT.md`](./docs/SECURITY_AUDIT.md).

Unified auth + tier + usage middleware for API products shipped across multiple marketplaces
(RapidAPI, Zyla, Postman, APYHub, ...).

Your business code only reads `request.state.billing.tier`. Adding a new marketplace = new
`ProxySecretAdapter(...)` instance + env vars. Zero code change.

See `docs/DESIGN.md` for full design.

## Install

```bash
# Pin a version from GitHub
pip install "api-billing-gateway[fastapi] @ git+https://github.com/lionwashington/api-billing-gateway.git@v0.1.0"

# Or editable from a local checkout
pip install -e .[fastapi]
```

## Minimal wiring

```python
from fastapi import FastAPI
from api_billing_gateway import BillingMiddleware, PlanTier
from api_billing_gateway.adapters import ProxySecretAdapter, StaticBearerAdapter

app = FastAPI()
app.add_middleware(
    BillingMiddleware,
    adapters=[
        ProxySecretAdapter(
            name="rapidapi",
            secret_value=os.environ["RAPIDAPI_PROXY_SECRET"],
            secret_header="X-RapidAPI-Proxy-Secret",
            user_header="X-RapidAPI-User",
            tier_header="X-RapidAPI-Subscription",
            tier_map={"BASIC": PlanTier.FREE, "PRO": PlanTier.STARTER,
                      "ULTRA": PlanTier.PRO, "MEGA": PlanTier.BUSINESS},
        ),
        StaticBearerAdapter(name="bearer", api_key=os.environ["API_KEY"]),
    ],
)
```

## Status

- v0.1 (current): `ProxySecretAdapter`, `StaticBearerAdapter`, `BillingMiddleware`.
- `TokenExchangeAdapter` stub (v0.2+).
- Stripe/NativeKey intentionally out of scope — see DESIGN §1.2.
