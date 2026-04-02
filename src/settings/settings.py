"""Typed application settings using Pydantic.

This module contains the Settings class with all configuration options
loaded from environment variables or .env file.
"""

from __future__ import annotations

import os
from typing import Any

from pydantic import AnyUrl, BaseModel, Field, ValidationError, ConfigDict

from .base import _resolve_env_file, _read_env_file


class Settings(BaseModel):
    """Typed SubSkin application settings.

    All settings are loaded from environment variables or .env file.
    """

    model_config = ConfigDict(
        extra="forbid",
        env_file=".env",
        env_file_encoding="utf-8",
        validate_default=True
    )

    NCBI_API_KEY: str | None = Field(
        default=None,
        description="PubMed/NCBI API key.",
    )
    OPENAI_API_KEY: str | None = Field(
        default=None,
        description="OpenAI API key for translation and summarization.",
    )
    SEMANTIC_SCHOLAR_API_KEY: str | None = Field(
        default=None,
        description="Semantic Scholar API key.",
    )
    ANTHROPIC_API_KEY: str | None = Field(
        default=None,
        description="Anthropic API for alternative LLM support.",
    )
    DATABASE_URL: AnyUrl | None = Field(
        default=None,
        description="Database connection URL for future PostgreSQL support.",
    )
    REDIS_URL: AnyUrl | None = Field(
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
    SMTP_USER: str | None = Field(
        default=None,
        description="SMTP username for email delivery.",
    )
    SMTP_PASSWORD: str | None = Field(
        default=None,
        description="SMTP password or app password.",
    )
    GITHUB_CLIENT_ID: str | None = Field(
        default=None,
        description="GitHub OAuth client ID.",
    )
    GITHUB_CLIENT_SECRET: str | None = Field(
        default=None,
        description="GitHub OAuth client secret.",
    )
    SECRET_KEY: str | None = Field(
        default=None,
        description="Session encryption secret key.",
    )
    JWT_SECRET_KEY: str | None = Field(
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
    QQ_BOT_ACCESS_TOKEN: str | None = Field(
        default=None,
        description="QQ bot access token.",
    )
    QQ_NOTIFICATION_GROUP: str | None = Field(
        default=None,
        description="QQ notification group ID.",
    )
    QQ_NOTIFICATION_ADMIN: str | None = Field(
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
    ALIYUN_OSS_BUCKET: str | None = Field(
        default=None,
        description="Alibaba Cloud OSS bucket name.",
    )
    ALIYUN_OSS_ACCESS_KEY_ID: str | None = Field(
        default=None,
        description="Alibaba Cloud OSS access key ID.",
    )
    ALIYUN_OSS_ACCESS_KEY_SECRET: str | None = Field(
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
    ALERT_EMAIL_RECIPIENT: str | None = Field(
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
    ALERT_EMAIL_SMTP_USER: str | None = Field(
        default=None,
        description="SMTP username for alert emails.",
    )
    ALERT_EMAIL_SMTP_PASSWORD: str | None = Field(
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
    WECHAT_OPENCLAW_TOKEN: str | None = Field(
        default=None,
        description="OpenClaw gateway authentication token.",
    )

    # Volcengine (火山引擎) OpenAI-compatible API
    VOLCENGINE_API_KEY: str | None = Field(
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
    def _load_values(cls, env_file: str | None | Path = None) -> dict[str, Any]:
        env_path = _resolve_env_file(env_file)
        file_values = _read_env_file(env_path)
        values: dict[str, Any] = {}
        for field_name in cls.model_fields:
            raw_value = os.getenv(field_name, file_values.get(field_name))
            if raw_value is not None:
                values[field_name] = raw_value

        return values

    @classmethod
    def from_env_file(cls, env_file: str | None | Path = None) -> Settings:
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
            if field_info.default is getattr(__import__('builtins'), '_UNSET', object()):
                if not hasattr(self, field_name) or getattr(self, field_name) is None:
                    missing.append(field_name)
        return missing

    def validate(self) -> bool:
        """Return True if all required fields are set."""
        return len(self.missing_keys()) == 0


settings = Settings()
