from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Optional, get_args, get_type_hints
from urllib.parse import urlparse

_UNSET = object()

try:
    from pydantic import AnyUrl, BaseModel, Field, ValidationError, ConfigDict
except ImportError:
    from dataclasses import dataclass

    class ValidationError(ValueError):
        pass

    class AnyUrl(str):
        pass

    def ConfigDict(**kwargs):
        return None

    @dataclass(frozen=True)
    class _FieldInfo:
        default: Any = _UNSET
        ge: Optional[int] = None
        le: Optional[int] = None
        pattern: Optional[str] = None
        description: Optional[str] = None

    def Field(
        default: Any = _UNSET,
        *,
        ge: Optional[int] = None,
        le: Optional[int] = None,
        pattern: Optional[str] = None,
        description: Optional[str] = None,
    ) -> _FieldInfo:
        return _FieldInfo(
            default=default,
            ge=ge,
            le=le,
            pattern=pattern,
            description=description,
        )

    class _BaseModelMeta(type):
        def __new__(
            mcls, name: str, bases: tuple[type, ...], namespace: dict[str, Any]
        ):
            cls = super().__new__(mcls, name, bases, namespace)
            annotations = get_type_hints(cls, include_extras=True)

            model_fields: dict[str, _FieldInfo] = {}
            for field_name, annotation in annotations.items():
                default = namespace.get(field_name, getattr(cls, field_name, _UNSET))
                if isinstance(default, _FieldInfo):
                    model_fields[field_name] = default
                else:
                    model_fields[field_name] = _FieldInfo(default=default)
            cls.model_fields = model_fields
            cls.__annotations__ = annotations
            return cls

    class BaseModel(metaclass=_BaseModelMeta):
        model_fields: dict[str, _FieldInfo]

        def __init__(self, **data: Any) -> None:
            errors: list[str] = []
            for field_name, field_info in self.model_fields.items():
                raw_value = (
                    data[field_name] if field_name in data else field_info.default
                )
                if raw_value is _UNSET:
                    raw_value = None

                try:
                    value = self._validate_field(
                        field_name,
                        raw_value,
                        self.__class__.__annotations__[field_name],
                        field_info,
                    )
                except ValidationError as exc:
                    errors.append(f"{field_name}: {exc}")
                    continue

                object.__setattr__(self, field_name, value)

            if errors:
                raise ValidationError("; ".join(errors))

        @classmethod
        def model_validate(cls, data: dict[str, Any]) -> BaseModel:
            return cls(**data)

        @staticmethod
        def _validate_field(
            field_name: str,
            value: Any,
            annotation: Any,
            field_info: _FieldInfo,
        ) -> Any:
            del field_name
            allow_none = False
            args = get_args(annotation)
            if args and type(None) in args:
                allow_none = True
                non_none = [arg for arg in args if arg is not type(None)]
                annotation = non_none[0] if non_none else Any

            if value is None:
                if (
                    allow_none
                    or field_info.default is None
                    or field_info.default is _UNSET
                ):
                    return None
                raise ValidationError("value is required")

            if annotation is bool:
                value = BaseModel._coerce_bool(value)
            elif annotation is int:
                try:
                    value = int(value)
                except (TypeError, ValueError) as exc:
                    raise ValidationError("value must be an integer") from exc
            elif annotation is str:
                value = str(value)
            elif (
                annotation is AnyUrl or getattr(annotation, "__name__", "") == "AnyUrl"
            ):
                value = BaseModel._validate_url(value)

            if annotation is int:
                if field_info.ge is not None and value < field_info.ge:
                    raise ValidationError(f"value must be >= {field_info.ge}")
                if field_info.le is not None and value > field_info.le:
                    raise ValidationError(f"value must be <= {field_info.le}")
            if annotation is str and field_info.pattern:
                if not re.fullmatch(field_info.pattern, value):
                    raise ValidationError("value does not match required pattern")

            return value

        @staticmethod
        def _coerce_bool(value: Any) -> bool:
            if isinstance(value, bool):
                return value
            if isinstance(value, int) and value in (0, 1):
                return bool(value)
            text = str(value).strip().lower()
            if text in {"true", "1", "yes", "y", "on"}:
                return True
            if text in {"false", "0", "no", "n", "off"}:
                return False
            raise ValidationError("value must be a boolean")

        @staticmethod
        def _validate_url(value: Any) -> AnyUrl:
            text = str(value).strip()
            parsed = urlparse(text)
            if not parsed.scheme or not parsed.netloc:
                raise ValidationError("value must be a valid URL")
            normalized = text if parsed.path else text.rstrip("/") + "/"
            return AnyUrl(normalized)


try:
    from dotenv import dotenv_values
except ImportError:
    dotenv_values = None


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _resolve_env_file(env_file: str | Optional[Path] = None) -> Path:
    candidate = env_file or os.getenv("ENV_FILE") or ".env"
    path = Path(candidate).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def _read_env_file(env_path: Path) -> dict[str, str]:
    if not env_path.exists():
        return {}

    if dotenv_values is not None:
        parsed = dotenv_values(dotenv_path=env_path, encoding="utf-8")
        return {key: value for key, value in parsed.items() if value is not None}

    values: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        key = key.strip()
        if not key:
            continue

        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]

        values[key] = value

    return values


class Settings(BaseModel):
    """Typed SubSkin application settings."""

    model_config = ConfigDict(
        extra="forbid",
        env_file=".env",
        env_file_encoding="utf-8",
        validate_default=True
    )

    NCBI_API_KEY: Optional[str] = Field(
        default=None,
        description="PubMed/NCBI API key.",
    )
    OPENAI_API_KEY: Optional[str] = Field(
        default=None,
        description="OpenAI API key for translation and summarization.",
    )
    SEMANTIC_SCHOLAR_API_KEY: Optional[str] = Field(
        default=None,
        description="Semantic Scholar API key.",
    )
    ANTHROPIC_API_KEY: Optional[str] = Field(
        default=None,
        description="Anthropic API key for alternative LLM support.",
    )
    DATABASE_URL: Optional[AnyUrl] = Field(
        default=None,
        description="Database connection URL for future PostgreSQL support.",
    )
    REDIS_URL: Optional[AnyUrl] = Field(
        default=None,
        description="Redis connection URL for caching and sessions.",
    )
    SITE_URL: AnyUrl = Field(
        default="https://subskin.example.com",
        description="Public website URL.",
    )
    SITE_NAME: str = Field(default="SubSkin", description="Public site name.")
    SITE_DESCRIPTION: str = Field(
        default="白癜风百科全书与社区",
        description="Public site description.",
    )
    SMTP_HOST: str = Field(
        default="smtp.gmail.com",
        description="SMTP server hostname for email digests.",
    )
    SMTP_PORT: int = Field(
        default=587,
        ge=1,
        le=65535,
        description="SMTP server port.",
    )
    SMTP_USER: Optional[str] = Field(
        default=None,
        description="SMTP username for email delivery.",
    )
    SMTP_PASSWORD: Optional[str] = Field(
        default=None,
        description="SMTP password or app password.",
    )
    GITHUB_CLIENT_ID: Optional[str] = Field(
        default=None,
        description="GitHub OAuth client ID.",
    )
    GITHUB_CLIENT_SECRET: Optional[str] = Field(
        default=None,
        description="GitHub OAuth client secret.",
    )
    SECRET_KEY: Optional[str] = Field(
        default=None,
        description="Session encryption secret key.",
    )
    JWT_SECRET_KEY: Optional[str] = Field(
        default=None,
        description="JWT signing secret key.",
    )
    LOG_LEVEL: str = Field(default="INFO", description="Application logging level.")
    LOG_FILE: str = Field(default="logs/subskin.log", description="Log file path.")
    SCHEDULER_ENABLED: bool = Field(
        default=True,
        description="Enable scheduled daily updates.",
    )
    DAILY_UPDATE_TIME: str = Field(
        default="02:00",
        pattern=r"^\d{2}:\d{2}$",
        description="Daily update execution time in UTC.",
    )
    UPDATE_RETRY_ATTEMPTS: int = Field(
        default=3,
        ge=0,
        description="Number of retries for update jobs.",
    )
    UPDATE_RETRY_DELAY: int = Field(
        default=300,
        ge=0,
        description="Retry delay in seconds.",
    )
    TRACK_INCREMENTAL_UPDATES: bool = Field(
        default=True,
        description="Track incremental updates.",
    )
    UPDATE_HISTORY_DAYS: int = Field(
        default=30,
        ge=0,
        description="Number of days to retain update history.",
    )
    QQ_BOT_ENABLED: bool = Field(
        default=True,
        description="Enable QQ bot notifications.",
    )
    QQ_BOT_API_URL: AnyUrl = Field(
        default="http://localhost:8080",
        description="Openclaw API URL for the QQ bot.",
    )
    QQ_BOT_ACCESS_TOKEN: Optional[str] = Field(
        default=None,
        description="QQ bot access token.",
    )
    QQ_NOTIFICATION_GROUP: Optional[str] = Field(
        default=None,
        description="QQ notification group ID.",
    )
    QQ_NOTIFICATION_ADMIN: Optional[str] = Field(
        default=None,
        description="QQ notification admin ID.",
    )
    ALIYUN_OSS_ENABLED: bool = Field(
        default=False,
        description="Enable Alibaba Cloud OSS storage.",
    )
    ALIYUN_OSS_ENDPOINT: str = Field(
        default="oss-cn-hangzhou.aliyuncs.com",
        description="Alibaba Cloud OSS endpoint.",
    )
    ALIYUN_OSS_BUCKET: Optional[str] = Field(
        default=None,
        description="Alibaba Cloud OSS bucket name.",
    )
    ALIYUN_OSS_ACCESS_KEY_ID: Optional[str] = Field(
        default=None,
        description="Alibaba Cloud OSS access key ID.",
    )
    ALIYUN_OSS_ACCESS_KEY_SECRET: Optional[str] = Field(
        default=None,
        description="Alibaba Cloud OSS access key secret.",
    )
    BACKUP_ENABLED: bool = Field(
        default=True,
        description="Enable automated backups.",
    )
    BACKUP_SCHEDULE: str = Field(
        default="0 3 * * *",
        description="Cron schedule for backups.",
    )
    BACKUP_RETENTION_DAYS: int = Field(
        default=7,
        ge=0,
        description="Number of days to keep backups.",
    )
    HEALTH_CHECK_ENABLED: bool = Field(
        default=True,
        description="Enable health checks.",
    )
    HEALTH_CHECK_PORT: int = Field(
        default=8080,
        ge=1,
        le=65535,
        description="Health check server port.",
    )
    METRICS_ENABLED: bool = Field(
        default=True,
        description="Enable metrics endpoint.",
    )
    METRICS_PORT: int = Field(
        default=9090,
        ge=1,
        le=65535,
        description="Metrics server port.",
    )
    WORKER_PROCESSES: int = Field(
        default=4,
        ge=1,
        description="Number of worker processes.",
    )
    MAX_CONCURRENT_TASKS: int = Field(
        default=10,
        ge=1,
        description="Maximum concurrent tasks.",
    )
    TASK_TIMEOUT_SECONDS: int = Field(
        default=3600,
        ge=1,
        description="Task timeout in seconds.",
    )
    RAW_DATA_RETENTION_DAYS: int = Field(
        default=90,
        ge=0,
        description="Retention days for raw data.",
    )
    PROCESSED_DATA_RETENTION_DAYS: int = Field(
        default=365,
        ge=0,
        description="Retention days for processed data.",
    )
    LOG_RETENTION_DAYS: int = Field(
        default=30,
        ge=0,
        description="Retention days for logs.",
    )
    ALERT_EMAIL_ENABLED: bool = Field(
        default=False,
        description="Enable alert emails.",
    )
    ALERT_EMAIL_RECIPIENT: Optional[str] = Field(
        default=None,
        description="Alert email recipient.",
    )
    ALERT_EMAIL_SMTP_HOST: str = Field(
        default="smtp.gmail.com",
        description="SMTP host for alert emails.",
    )
    ALERT_EMAIL_SMTP_PORT: int = Field(
        default=587,
        ge=1,
        le=65535,
        description="SMTP port for alert emails.",
    )
    ALERT_EMAIL_SMTP_USER: Optional[str] = Field(
        default=None,
        description="SMTP username for alert emails.",
    )
    ALERT_EMAIL_SMTP_PASSWORD: Optional[str] = Field(
        default=None,
        description="SMTP password for alert emails.",
    )

# WeChat Notification (via OpenClaw)
    WECHAT_NOTIFICATION_ENABLED: bool = Field(
        default=False,
        description="Enable WeChat notifications for daily updates.",
    )
    WECHAT_OPENCLAW_URL: str = Field(
        default="http://127.0.0.1:18789",
        description="OpenClaw gateway URL.",
    )
    WECHAT_OPENCLAW_TOKEN: Optional[str] = Field(
        default=None,
        description="OpenClaw gateway authentication token.",
    )

# Volcengine (火山引擎) OpenAI-compatible API
    VOLCENGINE_API_KEY: Optional[str] = Field(
        default=None,
        description="Volcengine API key for translation and summarization.",
    )
    VOLCENGINE_BASE_URL: str = Field(
        default="https://ark.cn-beijing.volces.com/api/v3",
        description="Volcengine API base URL.",
    )
    VOLCENGINE_MODEL: str = Field(
        default="doubao-4k",
        description="Volcengine model name.",
    )

    @classmethod
    def _load_values(cls, env_file: str | Optional[Path] = None) -> dict[str, Any]:
        env_path = _resolve_env_file(env_file)
        file_values = _read_env_file(env_path)
        values: dict[str, Any] = {}
        for field_name in cls.model_fields:
            raw_value = os.getenv(field_name, file_values.get(field_name))
            if raw_value is not None:
                values[field_name] = raw_value

        return values

    @classmethod
    def from_env_file(cls, env_file: str | Optional[Path] = None) -> Settings:
        return cls.model_validate(cls._load_values(env_file=env_file))

    def __init__(self, **data: Any) -> None:
        if not data:
            data = self.__class__._load_values()
        super().__init__(**data)
        if isinstance(getattr(self, "LOG_LEVEL", None), str):
            object.__setattr__(self, "LOG_LEVEL", self.LOG_LEVEL.strip().upper())

    def missing_keys(self) -> list[str]:
        """Return list of required keys that are missing."""
        missing = []
        for field_name, field_info in self.model_fields.items():
            # Check if field is required (no default value)
            if field_info.default is getattr(_UNSET, "_UNSET", None):
                if not hasattr(self, field_name) or getattr(self, field_name) is None:
                    missing.append(field_name)
        return missing

    def validate(self) -> bool:
        """Return True if all required fields are set."""
        return len(self.missing_keys()) == 0


settings = Settings()


__all__ = ["Settings", "ValidationError", "settings"]
