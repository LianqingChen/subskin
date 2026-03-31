"""OpenAI-based translator for medical paper abstracts.

This module provides a :class:`Translator` that translates English medical
paper abstracts into Chinese using the OpenAI Chat API.  It integrates
rate limiting, caching, and automatic retries for transient errors.

Example::

    from src.processors.translator import Translator

    translator = Translator(model="gpt-4")
    chinese_abstract = translator.translate(english_abstract)
"""

from __future__ import annotations

import hashlib
import logging
import os

from typing import Optional

import openai
from openai import OpenAI
from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import settings
from src.exceptions import APIError
from src.utils.cache import Cache
from src.utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

# System prompt engineered for accurate medical abstract translation.
_SYSTEM_PROMPT = (
    "你是一位专业的医学翻译专家，擅长将英文医学论文摘要翻译为中文。"
    "请遵循以下原则：\n"
    "1. 保留所有专业医学术语的准确性，必要时在中文翻译后用括号标注英文原文。\n"
    "2. 使用通俗易懂的语言，让非医学专业的读者也能理解。\n"
    "3. 保持原文的逻辑结构和信息完整性。\n"
    "4. 不添加任何医疗建议或个人意见。\n"
    "5. 仅输出翻译结果，不要添加额外的解释或说明。"
)

# OpenAI exception types that indicate transient failures worth retrying.
_RETRYABLE_ERRORS = (
    openai.RateLimitError,
    openai.APITimeoutError,
    openai.APIConnectionError,
    openai.InternalServerError,
)

# 30 days in seconds – translations are deterministic for the same input.
_DEFAULT_CACHE_TTL: float = 30.0 * 24 * 3600

# 10 requests per minute expressed as requests-per-second.
_DEFAULT_RATE_LIMIT: float = 10.0 / 60.0


class Translator:
    """Translate medical paper abstracts from English to Chinese via OpenAI-compatible API.

    Supports both OpenAI and Volcengine (火山引擎) API. When Volcengine API
    key is configured, it will be used automatically.

    Integrates :class:`~src.utils.rate_limiter.RateLimiter` to throttle API
    calls and :class:`~src.utils.cache.Cache` to avoid redundant requests for
    identical text.  Transient API errors (rate-limit, timeout, connection,
    server errors) are retried with exponential backoff.

    Args:
        model: Model identifier.
        api_key: API key.  Auto-discovers from environment settings.
        base_url: Base URL for the API.  Auto-discovers from environment settings.
        cache: :class:`Cache` instance for storing translations.  An in-memory
            cache is created when ``None``.
        rate_limiter: :class:`RateLimiter` instance.  Defaults to
            10 requests per minute.
        cache_ttl: Time-to-live for cached translations in seconds.
            Defaults to 30 days.
        max_retries: Maximum retry attempts for transient errors.
        system_prompt: Custom system prompt for the translation model.

    Raises:
        APIError: If no API key is available.

    Example::

        translator = Translator()
        translation = translator.translate(
            "Vitiligo is a chronic skin disorder..."
        )
    """

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        cache: Optional[Cache] = None,
        rate_limiter: Optional[RateLimiter] = None,
        cache_ttl: float = _DEFAULT_CACHE_TTL,
        max_retries: int = 3,
        system_prompt: str = _SYSTEM_PROMPT,
    ) -> None:
        # Auto-detect API configuration from settings
        if settings.VOLCENGINE_API_KEY:
            # Use Volcengine (火山引擎) API
            resolved_key = api_key or settings.VOLCENGINE_API_KEY
            resolved_base_url = base_url or settings.VOLCENGINE_BASE_URL
            resolved_model = model or settings.VOLCENGINE_MODEL
        else:
            # Fallback to OpenAI API
            resolved_key = api_key or os.getenv("OPENAI_API_KEY")
            resolved_base_url = base_url or "https://api.openai.com/v1"
            resolved_model = model or "gpt-3.5-turbo"

        if not resolved_key:
            raise APIError("No API key configured. Please set either OPENAI_API_KEY or VOLCENGINE_API_KEY")

        self._client = OpenAI(api_key=resolved_key, base_url=resolved_base_url)
        self._model = resolved_model
        self._cache = cache or Cache()
        self._rate_limiter = rate_limiter or RateLimiter(_DEFAULT_RATE_LIMIT)
        self._cache_ttl = cache_ttl
        self._max_retries = max_retries
        self._system_prompt = system_prompt

    @staticmethod
    def _cache_key(text: str) -> str:
        """Return a deterministic cache key for *text*.

        Uses SHA-256 to produce a fixed-length key regardless of input size.

        Args:
            text: Source text to hash.

        Returns:
            String of the form ``translate:<sha256_hex>``.
        """
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return f"translate:{digest}"

    def _call_openai(self, text: str) -> str:
        """Send a single translation request to the OpenAI chat API.

        Retryable exceptions are re-raised as-is so that the caller's retry
        logic (tenacity) can catch and retry them.  Non-retryable OpenAI
        errors are wrapped in :class:`~src.exceptions.APIError`.

        Args:
            text: English text to translate.

        Returns:
            Translated Chinese text.

        Raises:
            openai.RateLimitError: Retryable – OpenAI rate limit hit.
            openai.APITimeoutError: Retryable – request timed out.
            openai.APIConnectionError: Retryable – connection failed.
            openai.InternalServerError: Retryable – 5xx server error.
            APIError: Non-retryable API or response error.
        """
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": self._system_prompt},
                    {
                        "role": "user",
                        "content": (f"请将以下英文医学论文摘要翻译为中文：\n\n{text}"),
                    },
                ],
                temperature=0.1,
            )
        except _RETRYABLE_ERRORS:
            raise
        except openai.OpenAIError as exc:
            raise APIError(f"OpenAI error: {exc}", cause=exc) from exc

        if not response.choices:
            raise APIError("OpenAI returned no choices")

        content = response.choices[0].message.content
        if content is None:
            raise APIError("OpenAI returned empty content")

        return content.strip()

    def translate(self, text: str) -> str:
        """Translate an English medical abstract to Chinese.

        The method follows this sequence:

        1. Check the cache for a previous translation of *text*.
        2. On a cache miss, acquire a rate-limiter token.
        3. Call the OpenAI API, retrying on transient errors with
           exponential backoff.
        4. Store the successful translation in the cache.

        Args:
            text: English abstract to translate.

        Returns:
            Chinese translation string.

        Raises:
            ValueError: If *text* is empty or whitespace-only.
            APIError: If the translation fails after all retry attempts or
                encounters a non-retryable error.
        """
        if not text or not text.strip():
            raise ValueError("text must not be empty")

        text = text.strip()
        key = self._cache_key(text)

        cached = self._cache.get(key)
        if cached is not None:
            logger.debug("Cache hit for key %s", key)
            return str(cached)

        logger.debug("Cache miss for key %s – calling OpenAI API", key)

        self._rate_limiter.acquire()

        try:
            for attempt in Retrying(
                retry=retry_if_exception_type(_RETRYABLE_ERRORS),
                stop=stop_after_attempt(self._max_retries),
                wait=wait_exponential(multiplier=1, min=1, max=60),
                reraise=True,
            ):
                with attempt:
                    translation = self._call_openai(text)
        except _RETRYABLE_ERRORS as exc:
            raise APIError(
                f"Translation failed after {self._max_retries} retries: {exc}",
                cause=exc,
            ) from exc

        self._cache.set(key, translation, ttl=self._cache_ttl)
        logger.info("Translation cached for key %s", key)

        return translation
