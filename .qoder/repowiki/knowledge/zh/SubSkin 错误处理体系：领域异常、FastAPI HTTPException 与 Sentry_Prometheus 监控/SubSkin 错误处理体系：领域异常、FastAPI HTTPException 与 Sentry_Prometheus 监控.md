---
kind: error_handling
name: SubSkin 错误处理体系：领域异常、FastAPI HTTPException 与 Sentry/Prometheus 监控
category: error_handling
scope:
    - '**'
source_files:
    - src/exceptions.py
    - web/backend/exceptions.py
    - web/backend/app/middleware/rate_limit.py
    - web/backend/services/monitoring.py
    - web/backend/app/main.py
    - src/crawlers/clinical_trials_crawler.py
    - src/crawlers/cma_crawler.py
    - src/crawlers/pubmed_crawler.py
    - web/backend/api/user.py
    - web/backend/services/credential.py
    - tests/test_exceptions.py
---

## 1. 整体方案

SubSkin 采用「分层异常 + FastAPI HTTP 响应 + 外部监控」的组合策略：
- **爬虫/数据处理层**（`src/exceptions.py`）定义 `CrawlerError` 及其子类 `APIError`、`RateLimitError`、`CacheError`，用于爬虫模块的运行时错误。
- **Web 后端服务层**（`web/backend/exceptions.py`）定义业务异常基类 `SubSkinException` 及具体领域异常 `CredentialConflictError`、`CredentialNotFoundError`，由 service 抛出、API 层捕获并转为 HTTP 响应。
- **HTTP 层**：各 API 路由直接 `raise HTTPException(status_code=..., detail=...)`，没有全局 `@app.exception_handler` 统一处理器；429 通过中间件 `web/backend/app/middleware/rate_limit.py` 中的 `ReadRateLimit` / `WriteRateLimit` / `ChatRateLimit` 依赖统一拦截。
- **监控告警**：`web/backend/services/monitoring.py` 提供 `init_sentry(app)` 集成 Sentry（FastApiIntegration + StarletteIntegration + SqlalchemyIntegration），并提供 `capture_exception()` 手动上报；可选 Prometheus 指标中间件在请求级记录状态码。
- **CLI/脚本**：使用 Python 内置 `ValueError` / `RuntimeError` 做参数校验与不可达分支保护，无自定义异常体系。

## 2. 关键文件与包

| 职责 | 文件 | 说明 |
|---|---|---|
| 爬虫异常 | `src/exceptions.py` | `CrawlerError` 基类 + `APIError` / `RateLimitError` / `CacheError` |
| Web 业务异常 | `web/backend/exceptions.py` | `SubSkinException` + 凭证相关领域异常 |
| 速率限制中间件 | `web/backend/app/middleware/rate_limit.py` | 进程内令牌桶，按 IP / user_id 限流，抛 `HTTP 429` |
| 监控/Sentry | `web/backend/services/monitoring.py` | `init_sentry`、`capture_exception`、`PrometheusMiddleware` |
| FastAPI 入口 | `web/backend/app/main.py` | 注册 CORS、Sentry、Prometheus，挂载所有路由 |
| 爬虫实现 | `src/crawlers/*.py` | 多处 `raise APIError(...)` 或 `raise ValueError(...)` 参数校验 |
| 测试 | `tests/test_exceptions.py` | 验证爬虫异常继承关系 |

## 3. 架构与约定

### 3.1 爬虫层异常
- `CrawlerError(Exception)` 作为爬虫域根异常，构造时接受 `message` 和可选 `cause`，并通过 `self.__cause__` 保留底层异常链。
- 子类 `APIError`、`RateLimitError`、`CacheError` 仅用于区分失败原因；调用方通过 `except APIError as exc:` 捕获（见 `src/crawlers/clinical_trials_crawler.py` 中重试逻辑）。
- 参数校验直接使用 `ValueError("...")`（如 `cma_crawler.py`、`pubmed_crawler.py` 对 `max_pages`、`page_size` 等参数的断言式检查）。

### 3.2 Web 后端异常
- Service 层（如 `services/credential.py`）抛出 `CredentialConflictError` / `CredentialNotFoundError` 等业务异常。
- API 层（如 `api/user.py`）显式 `except CredentialConflictError as e:` 将其转换为 `HTTPException` 返回给前端。
- 大量路由直接 `raise HTTPException(status_code=400/401/403/404/500/504, detail=...)`，未封装统一的错误码枚举。

### 3.3 速率限制
- `rate_limit.py` 用进程内 `defaultdict(list)` 维护时间窗内的请求时间戳，重启即清空。
- 读接口按 IP 限流（60 次/分钟），写接口按 user_id/IP 限流（10 次/分钟），RAG chat 按 user_id/IP 限流（20 次/分钟）。
- 超限统一抛 `HTTP 429 TOO_MANY_REQUESTS`，detail 为中文提示。

### 3.4 监控与可观测性
- `init_sentry(app)` 仅在 `SENTRY_DSN` 存在时启用，自动集成 FastAPI、Starlette、SQLAlchemy；`before_send` 过滤 `password/token/secret/api_key/authorization` 等敏感头。
- `capture_exception(error, context)` 允许在任意位置手动上报异常并附加上下文。
- Prometheus 中间件可选启用（`PROMETHEUS_ENABLED=true`），记录 `http_requests_total`（按 method/endpoint/status_code）、`http_request_duration_seconds`、`http_requests_in_progress`，并在 `/metrics` 暴露。

### 3.5 CLI / 脚本层
- 脚本（`scripts/*.py`）普遍使用 `try/except Exception as e:` 包裹单条任务，失败后记录日志继续处理下一条，体现「批处理容错」模式。
- 配置参数校验使用 `ValueError`，不可达分支使用 `RuntimeError`。

## 4. 约定与约束

- **爬虫异常必须继承 `CrawlerError`**：`src/exceptions.py` 定义了该层次结构，`tests/test_exceptions.py` 通过断言 `isinstance(exc, CrawlerError)` 强制子类关系。
- **Web 业务异常必须继承 `SubSkinException`**：`web/backend/exceptions.py` 中 `CredentialConflictError` / `CredentialNotFoundError` 均继承自 `SubSkinException`，service 层统一抛出，API 层统一捕获。
- **限流错误统一 429**：所有速率限制路径通过 `HTTPException(status_code=429, detail=...)` 返回，不混用其他状态码。
- **Sentry 初始化是幂等的**：未配置 `SENTRY_DSN` 时静默跳过，缺失 `sentry-sdk` 时记录 warning 并返回 False，保证部署环境可降级运行。
- **Prometheus 中间件可关闭**：仅在环境变量开启时注入，且内部 `prometheus-client` 缺失时降级为 disabled，不影响主流程。
- **无全局异常处理器**：代码库中未发现 `@app.exception_handler` 装饰器，HTTP 错误由各路由自行 raise，因此新增 API 时必须显式处理异常。
- **参数校验优先使用 `ValueError`**：爬虫与模型层的非法参数通过 `ValueError("...")` 表达，而非自定义异常类型。

## 5. 已知缺口

- Web 后端缺少统一的 `HTTPException` 转换器（例如将 `SubSkinException` 映射为带 code/detail 的统一 JSON 响应），新增业务异常需在各 API 路由中重复 try/except。
- 爬虫异常未在 CLI 入口统一收敛，`src/cli.py` 仅以 `except Exception as e:` 兜底打印，未区分 `CrawlerError` 与其他异常。
- 脚本层缺乏结构化错误码，全部使用通用 `Exception` 捕获，不利于自动化区分失败类型。