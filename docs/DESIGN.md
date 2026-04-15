# api-billing-gateway — DESIGN v0.1

> 独立 Python 包。把"API 产品 × 计费/分发平台"之间的鉴权 + 配额 + 计量抽成一层中间件，让业务代码只认 `AuthContext.tier`，不关心来源是 RapidAPI、Zyla 还是 APYHub。

---

## 1. 目标 & 非目标

### 1.1 目标（v0.1）
- 一套 FastAPI middleware，支持多个 API marketplace 同时上架同一套业务代码。
- `ProxySecretAdapter` 覆盖 Top 3 平台：**Zyla / Postman / APYHub**（以及已经在跑的 RapidAPI），全部靠配置切换，不改业务代码。
- `StaticBearerAdapter` 覆盖自运维 Bearer token（= scanner 当前的直连通道）。
- 统一的 `AuthContext`（source / external_user_id / tier / raw_tier / mode）挂到 `request.state.billing`。
- 不绑定任何具体业务语义（不负责 tier→model / tier→quota 的映射，这些留给调用方）。

### 1.2 非目标（v0.1 明确砍掉）
- ❌ Stripe / 自建 SaaS 计费（NativeKey 通道）。"第一期先搞各个现成 API 平台"（Lion 决策 C）。
- ❌ OAuth / token-exchange 流程（见 §4.3，仅留骨架）。
- ❌ 自己搞 dashboard / 订阅管理 UI（marketplace 已经做了）。
- ❌ 跨业务的共用配额存储（每个业务自己决定是否要 Redis / DB，abg 只提供 hook）。

---

## 2. 核心抽象

### 2.1 `PlanTier`
```python
class PlanTier(str, Enum):
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    BUSINESS = "business"
```
4 档统一语义。平台各自的订阅名（BASIC/PRO/ULTRA/MEGA、Free/Starter/Pro/Enterprise…）由 adapter 的 `tier_map` 负责翻译。

### 2.2 `AuthContext`
```python
@dataclass(frozen=True)
class AuthContext:
    source: str            # "rapidapi" / "zyla" / "apyhub" / "bearer" …
    external_user_id: str  # marketplace user id，或 bearer token 的 hash 前缀
    tier: PlanTier         # 归一后的档位
    raw_tier: str          # 平台原始档位字符串（审计 + 未来扩展）
    mode: str              # "authed" | "disabled-test"
```
业务代码只读 `request.state.billing: AuthContext`。

### 2.3 `BillingAdapter` Protocol
```python
class BillingAdapter(Protocol):
    name: str
    def matches(self, request: Request) -> bool: ...
    def authenticate(self, request: Request) -> AuthContext | None: ...
    async def report_usage(self, ctx: AuthContext, units: int = 1) -> None: ...
```
- `matches()`：便宜的 header 嗅探，O(1)。
- `authenticate()`：验证 + 构造 `AuthContext`；失败抛 `AuthError`。
- `report_usage()`：给需要回报用量的平台留 hook；v0.1 的 Proxy-Secret 类平台全部 no-op（marketplace 自己记账）。

---

## 3. 中间件

```python
class BillingMiddleware:
    def __init__(
        self,
        app,
        adapters: list[BillingAdapter],
        *,
        auth_enabled: bool = True,
        exempt_paths: set[str] = {"/health", "/docs", "/openapi.json", "/redoc"},
        protected_prefix: str = "/api/",
    ): ...
```
流程：
1. `auth_enabled=False` → 构造 `mode="disabled-test"` 的 `AuthContext`（tier=FREE），挂到 state，直接放行。仅 dev 使用。
2. 路径豁免（health/docs）→ 直接放行。
3. 非 protected_prefix → 直接放行。
4. 遍历 adapters，第一个 `matches()` 的负责 `authenticate()`。
5. 成功 → `request.state.billing = ctx`，放行；失败 → 401/403。
6. 全部不 match → 401。

**顺序很重要**：ProxySecret 类 adapter 放前面（header 指纹强），StaticBearer 放最后（兜底）。

---

## 4. Adapter 实现

### 4.1 `ProxySecretAdapter`（v0.1 核心，覆盖 Zyla / Postman / APYHub / RapidAPI）
```python
ProxySecretAdapter(
    name="rapidapi",
    secret_value=os.environ["RAPIDAPI_PROXY_SECRET"],
    secret_header="X-RapidAPI-Proxy-Secret",
    user_header="X-RapidAPI-User",
    tier_header="X-RapidAPI-Subscription",
    tier_map={"BASIC": PlanTier.FREE, "PRO": PlanTier.STARTER,
              "ULTRA": PlanTier.PRO, "MEGA": PlanTier.BUSINESS},
    default_tier=PlanTier.FREE,
)
```
**全部参数化**。新平台 = 新实例，零代码。  
Zyla / APYHub / Postman 只要平台会注入一个「共享 secret + 用户标识 + 订阅档位」三件套，就直接复用。文档见 `docs/research/API_BILLING_PLATFORMS.md` §4。

### 4.2 `StaticBearerAdapter`（scanner 直连通道）
```python
StaticBearerAdapter(
    name="bearer",
    api_key=os.environ["API_KEY"],
    default_tier=PlanTier.PRO,
)
```
替代 scanner 当前 `app/auth.py` 里手写的 `Authorization: Bearer <API_KEY>` 分支。tier 固定（运维自用）。

### 4.3 `TokenExchangeAdapter`（v0.1 仅骨架）
```python
class TokenExchangeAdapter:
    """v0.2+：OAuth / marketplace 签发的短 token 换 user+tier。
    典型场景：AWS Marketplace、Google API Gateway。
    """
    def matches(self, request): return False  # v0.1 永远不 match
    def authenticate(self, request):
        raise NotImplementedError("TokenExchangeAdapter planned for v0.2")
    async def report_usage(self, ctx, units=1):
        raise NotImplementedError
```
留骨架 = 让 v0.2 扩展时不用改 Protocol。Lion 决策 D。

### 4.4 （已砍）NativeKeyAdapter / Stripe
v0.1 不做。未来要做的时候，Stripe 场景其实是 `StaticBearer × 配额后端`——先把 abg 的 Adapter protocol 跑稳，再叠配额层，不要反过来。

---

## 5. 配置 & 使用

### 5.1 业务侧装配（scanner 示例）
```python
from api_billing_gateway import BillingMiddleware, PlanTier
from api_billing_gateway.adapters import ProxySecretAdapter, StaticBearerAdapter

adapters = []
if os.getenv("RAPIDAPI_PROXY_SECRET"):
    adapters.append(ProxySecretAdapter(
        name="rapidapi",
        secret_value=os.environ["RAPIDAPI_PROXY_SECRET"],
        secret_header="X-RapidAPI-Proxy-Secret",
        user_header="X-RapidAPI-User",
        tier_header="X-RapidAPI-Subscription",
        tier_map={"BASIC": PlanTier.FREE, "PRO": PlanTier.STARTER,
                  "ULTRA": PlanTier.PRO, "MEGA": PlanTier.BUSINESS},
    ))
if os.getenv("ZYLA_PROXY_SECRET"):
    adapters.append(ProxySecretAdapter(name="zyla", ...))
if os.getenv("API_KEY"):
    adapters.append(StaticBearerAdapter(name="bearer", api_key=os.environ["API_KEY"]))

app.add_middleware(
    BillingMiddleware,
    adapters=adapters,
    auth_enabled=os.getenv("AUTH_ENABLED", "true").lower() == "true",
)
```

### 5.2 业务代码读取 tier
```python
@router.post("/scan/sync")
async def scan(request: Request, body: ScanRequest):
    ctx: AuthContext = request.state.billing
    base, key, model = settings.resolve_llm(ctx.tier.value)  # tier→model 在业务层
    ...
```
**tier→model / tier→quota 的映射留在业务层**。不同产品（scanner、explainer、honeypot）对同一 tier 可以用不同模型或不同配额，abg 不越权。

---

## 6. 测试策略

- 每个 adapter：`matches` + `authenticate`（成功/失败/档位映射/大小写/空白）单测。
- `BillingMiddleware`：auth_enabled 开关、exempt_paths、protected_prefix、adapter 顺序、全未命中 → 401。
- 集成：挂一个假 FastAPI app，TestClient 模拟各 marketplace header，验证 `request.state.billing` 正确填充。
- Scanner 迁移验收：现有 29 个 pytest 保持全绿。

---

## 7. 工作量估算（v0.1，砍掉 Stripe 后）

| 模块 | 估时 |
|---|---|
| tier / context / Protocol | 0.5h |
| ProxySecretAdapter + 单测 | 2h |
| StaticBearerAdapter + 单测 | 1h |
| TokenExchangeAdapter 骨架 | 0.2h |
| BillingMiddleware + 集成测试 | 3h |
| pyproject / README / 打包 | 1h |
| Scanner 迁移 + 保 29 测试绿 | 2h |
| 文档收尾 | 0.3h |
| **合计** | **~10h** |

---

## 8. 发布

- v0.1：`freelancer/` monorepo 内 path dep（`pip install -e ../api-billing-gateway`）。
- v0.2：若第二个业务（explainer / honeypot）上线后稳定，再考虑发 PyPI 或私有 index。
- 版本号遵循 SemVer；Protocol 的 breaking change 必须 bump major。

---

## 9. 开放问题（留给 v0.2+）
- 配额回报：是否要一个可选的 Redis backend？—— 等第二个业务来驱动。
- 多租户 audit log：adapter 层 hook vs 业务层决定 —— 倾向 adapter 层提供可选 sink。
- `report_usage` 异步 vs fire-and-forget：目前 async def no-op，真用起来再定。
