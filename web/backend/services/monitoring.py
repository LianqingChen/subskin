"""
监控告警配置

集成 Sentry 错误追踪和 Prometheus 指标收集。

配置方式 (环境变量):
    SENTRY_DSN=https://xxx@sentry.io/xxx  # Sentry DSN
    SENTRY_ENVIRONMENT=production  # 环境名称
    SENTRY_TRACES_SAMPLE_RATE=0.1  # 追踪采样率
    PROMETHEUS_ENABLED=true  # 是否启用 Prometheus 指标
"""

import logging
import os
import time
from functools import wraps
from typing import Optional

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


# ── Sentry Integration ──


def init_sentry(app: Optional[FastAPI] = None):
    """初始化 Sentry 错误追踪
    
    需要安装: pip install sentry-sdk[fastapi]
    """
    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        logger.info("Sentry DSN not configured, skipping initialization")
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

        environment = os.getenv("SENTRY_ENVIRONMENT", "development")
        traces_sample_rate = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1"))

        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            traces_sample_rate=traces_sample_rate,
            integrations=[
                StarletteIntegration(),
                FastApiIntegration(),
                SqlalchemyIntegration(),
            ],
            # 过滤敏感信息
            before_send=_filter_sensitive_data,
        )
        logger.info("Sentry initialized: environment=%s", environment)
        return True
    except ImportError:
        logger.warning("sentry-sdk not installed, skipping Sentry initialization")
        return False


def _filter_sensitive_data(event, hint):
    """过滤 Sentry 事件中的敏感数据"""
    # 移除密码、token 等敏感字段
    sensitive_keys = {"password", "token", "secret", "api_key", "authorization"}
    
    if "request" in event and "headers" in event["request"]:
        headers = event["request"]["headers"]
        for key in list(headers.keys()):
            if key.lower() in sensitive_keys:
                headers[key] = "[Filtered]"
    
    return event


def capture_exception(error: Exception, context: Optional[dict] = None):
    """手动捕获异常并发送到 Sentry"""
    try:
        import sentry_sdk
        with sentry_sdk.push_scope() as scope:
            if context:
                for key, value in context.items():
                    scope.set_extra(key, value)
            sentry_sdk.capture_exception(error)
    except ImportError:
        logger.error("Sentry not available: %s", error)


# ── Prometheus Metrics ──


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Prometheus 指标收集中间件
    
    收集以下指标:
    - http_requests_total: 请求总数 (按方法、路径、状态码分组)
    - http_request_duration_seconds: 请求耗时
    - http_requests_in_progress: 当前进行中的请求数
    """

    def __init__(self, app, enabled: bool = True):
        super().__init__(app)
        self.enabled = enabled
        self._metrics_initialized = False
        self._request_counter = None
        self._request_duration = None
        self._requests_in_progress = None

    def _init_metrics(self):
        if self._metrics_initialized:
            return
        try:
            from prometheus_client import Counter, Histogram, Gauge

            self._request_counter = Counter(
                "http_requests_total",
                "Total HTTP requests",
                ["method", "endpoint", "status_code"],
            )
            self._request_duration = Histogram(
                "http_request_duration_seconds",
                "HTTP request duration in seconds",
                ["method", "endpoint"],
                buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
            )
            self._requests_in_progress = Gauge(
                "http_requests_in_progress",
                "Number of HTTP requests in progress",
                ["method"],
            )
            self._metrics_initialized = True
            logger.info("Prometheus metrics initialized")
        except ImportError:
            logger.warning("prometheus-client not installed, metrics disabled")
            self.enabled = False

    async def dispatch(self, request: Request, call_next):
        if not self.enabled:
            return await call_next(request)

        self._init_metrics()
        if not self._metrics_initialized:
            return await call_next(request)

        method = request.method
        # 使用路由路径而不是实际路径，避免高基数
        endpoint = self._get_endpoint(request)

        self._requests_in_progress.labels(method=method).inc()
        start_time = time.time()

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            status_code = 500
            raise
        finally:
            duration = time.time() - start_time
            self._request_counter.labels(
                method=method, endpoint=endpoint, status_code=status_code
            ).inc()
            self._request_duration.labels(method=method, endpoint=endpoint).observe(
                duration
            )
            self._requests_in_progress.labels(method=method).dec()

        return response

    def _get_endpoint(self, request: Request) -> str:
        """获取规范化的端点名称"""
        # 使用路由模板而不是实际路径
        if request.scope.get("route"):
            return request.scope["route"].path
        # 回退到路径的第一段
        path = request.url.path
        parts = path.strip("/").split("/")
        return "/" + parts[0] if parts and parts[0] else "/"


def setup_prometheus_endpoint(app: FastAPI):
    """添加 /metrics 端点供 Prometheus 抓取"""
    if os.getenv("PROMETHEUS_ENABLED", "false").lower() != "true":
        return

    try:
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

        @app.get("/metrics", include_in_schema=False)
        async def metrics():
            return Response(
                content=generate_latest(),
                media_type=CONTENT_TYPE_LATEST,
            )

        logger.info("Prometheus /metrics endpoint enabled")
    except ImportError:
        logger.warning("prometheus-client not installed, /metrics endpoint disabled")


# ── Health Check ──


def setup_health_check(app: FastAPI):
    """添加健康检查端点"""

    @app.get("/api/health", include_in_schema=False)
    async def health_check():
        """健康检查端点"""
        from web.backend.database.database import engine
        from sqlalchemy import text

        status = {"status": "healthy", "checks": {}}

        # 检查数据库连接
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            status["checks"]["database"] = "ok"
        except Exception as e:
            status["status"] = "unhealthy"
            status["checks"]["database"] = f"error: {str(e)}"

        # 检查磁盘空间
        try:
            import shutil
            total, used, free = shutil.disk_usage("/")
            if free < 1024 * 1024 * 100:  # < 100MB
                status["status"] = "degraded"
                status["checks"]["disk"] = f"low space: {free // 1024 // 1024}MB"
            else:
                status["checks"]["disk"] = "ok"
        except Exception:
            status["checks"]["disk"] = "unknown"

        return status


# ── Initialization ──


def init_monitoring(app: FastAPI):
    """初始化所有监控组件"""
    # Sentry
    init_sentry(app)

    # Prometheus middleware
    if os.getenv("PROMETHEUS_ENABLED", "false").lower() == "true":
        app.add_middleware(PrometheusMiddleware, enabled=True)
        setup_prometheus_endpoint(app)

    # Health check
    setup_health_check(app)

    logger.info("Monitoring initialized")
