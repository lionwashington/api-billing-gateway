# abg Security Audit — "No Credential Storage" Verification

**Audit date**: 2026-04-15
**Scope**: `src/api_billing_gateway/` 全部源码 + `tests/`
**Objective**: 验证方案 B 承诺——abg 独立 public repo，且**不存任何 credential**（key/token 全部由上游调用方传入）。

---

## 1. 审计方法

- 源码静态扫描：`os.getenv` / `os.environ` / `open(` / `logger` / `logging` / `print(` / `.write(`
- 逐 adapter 审：构造函数签名、内部状态字段、认证路径、usage 上报路径
- 测试用例：是否只用 fake secret（fixture）还是混入真值

---

## 2. 各模块审计

### 2.1 `ProxySecretAdapter` (`adapters/proxy_secret.py`)

| 项 | 结果 |
|---|---|
| 构造签名 | 全 kw-only：`name`、`secret_value`、`secret_header`、`user_header`、`tier_header`、`tier_map`、`default_tier` — **secret 由调用方传入** |
| 内部状态 | `self._secret_value` 保存为对象字段（对象生命周期内）。**无 module-level / 全局状态。无 env 读取。无磁盘落盘。** |
| credential 流向 | `request.headers[self._secret_header]` ⇆ `self._secret_value` 直接比较 → 匹配成功后丢弃。**不写日志、不写磁盘、不返回到 AuthContext。** |
| AuthError detail | 仅 `f"{self.name}: invalid proxy secret"`——**不含 secret 值**。 |
| report_usage | 空实现（marketplace 侧已计量）——无任何副作用。 |

✅ **Pass**。

### 2.2 `StaticBearerAdapter` (`adapters/static_bearer.py`)

| 项 | 结果 |
|---|---|
| 构造签名 | kw-only：`name`、`api_key`、`default_tier`、`tier_header`、`tier_map` — **api_key 由调用方传入** |
| 内部状态 | `self._api_key` 对象字段。**无 env 读取、无磁盘落盘、无全局状态。** |
| credential 流向 | `Authorization: Bearer` header 解析 → 与 `self._api_key` 比较 → `external_user_id = "bearer:" + sha256(token)[:12]`，**外发 ID 用哈希前缀，非原 token**。 |
| AuthError detail | 仅 `f"{self.name}: invalid bearer token"`——**不回显 token**。 |
| report_usage | 空实现。 |

✅ **Pass**。

### 2.3 `TokenExchangeAdapter` (`adapters/token_exchange.py`)

| 项 | 结果 |
|---|---|
| 实现状态 | v0.1 骨架，`matches` 恒 `False`，`authenticate` / `report_usage` 抛 `NotImplementedError`。 |
| credential 存储 | 无字段、无构造参数、无状态。 |

✅ **Pass**（当前完全不接触 credential；v0.2+ 实装时需重新审）。

### 2.4 `BillingMiddleware` (`middleware.py`)

| 项 | 结果 |
|---|---|
| 构造签名 | `adapters`（列表）、`auth_enabled`、`exempt_paths`、`protected_prefix`——**无任何 credential 参数**。 |
| 内部状态 | adapter 列表 + 白名单路径 + 布尔开关。无 secret。 |
| dispatch 行为 | 委派给 adapter；`AuthError` 只返回 `e.detail`（已确认 adapter 侧 detail 不含原值）。**不记日志、不落盘。** |

✅ **Pass**。

### 2.5 `context.py` / `tier.py` / `__init__.py`

- `AuthContext` 字段：`source` / `external_user_id` / `tier` / `raw_tier` / `mode`——**无 credential 字段**。
- `tier.py` 只含枚举。
- `__init__.py` 只做 re-export。

✅ **Pass**。

### 2.6 扫描结果：`os.getenv` / `os.environ` / `open(` / `logger` / `print(` / `.write(`

```
src/api_billing_gateway/**  → 0 matches
```

**所有 env 读取、示例代码、I/O 调用都只出现在 `README.md` 和 `docs/DESIGN.md` 的示例片段中**（调用方职责），包源码本身零 I/O / 零 env。

### 2.7 测试 fixtures (`tests/`)

| 文件 | 使用的 "secret" | 判定 |
|---|---|---|
| `test_static_bearer.py` | `"key1"` / `"sekret"` | fake fixture |
| `test_proxy_secret.py` | `"s3cret"` / `"correct"` / `"wrong"` | fake fixture |
| `test_middleware.py` | `"proxy123"` / `"bearer123"` | fake fixture |

✅ **无硬编码真 secret**。

---

## 3. 问题清单

### 必须修
**无。**

### 建议修（非阻塞）
1. *（低优）* `BillingMiddleware.dispatch` 里 `AuthError` 走 `JSONResponse` 返回，建议 future 加一行显式不记录 sent header 的注释，防止后来人误加 `logger.warning(request.headers)` 类调试代码。当前状态安全。
2. *（低优）* `README.md` / `DESIGN.md` 示例统一用 `os.environ["X"]`（fail-fast）而不是 `os.getenv("X")`，避免调用方误传 `None` 进入 adapter 构造函数——构造函数已有 `if not secret_value: raise` 兜底，所以纯美化建议。

---

## 4. 结论

**当前状态满足"不存 credential"承诺。**

- ✅ 包源码不读 env、不写磁盘、不记日志。
- ✅ 所有 credential 通过构造函数参数由**调用方传入**，仅在 adapter 对象生命周期内保存为实例字段。
- ✅ 认证失败的错误消息**不回显**原 secret / token 值。
- ✅ `StaticBearerAdapter` 外发 `external_user_id` 用 sha256 前缀，不泄露原 token。
- ✅ 测试套件全部使用 fake fixture。
- ✅ `TokenExchangeAdapter` 当前无状态骨架（v0.2+ 实装时需重新审）。

**适合以 public repo 形式对外发布。**

---

## 5. Public 发布前补充建议（与本次审计分离，供 Lion 决策）

- LICENSE（建议 MIT / Apache-2.0）
- `README.md` 顶部加一行"No credential storage by design"说明 + 指向本审计报告
- CI 加 secret-scan（gitleaks / truffleHog）作为 public repo 的长期防线
- `pyproject.toml` author / urls 确认无内部信息
