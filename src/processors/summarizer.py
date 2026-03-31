"""OpenAI-powered summarizer for medical paper abstracts.

Generates patient-friendly Chinese summaries of vitiligo research papers,
extracting key treatment methods, results, and conclusions.

Supports both OpenAI and Volcengine (火山引擎) OpenAI-compatible API.
"""

from __future__ import annotations

from typing import Optional

import hashlib
import logging
import os
import time

from openai import APIConnectionError, APITimeoutError, OpenAI, RateLimitError

from src.config import settings
from src.utils.cache import Cache
from src.utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

_DEFAULT_CACHE_TTL: float = 30 * 24 * 3600  # 30 days
_DEFAULT_RATE_LIMIT: float = 10.0 / 60.0  # 10 req/min → req/s

_SYSTEM_PROMPT = (
    "你是一位专业的医学科普写作助手，专注于白癜风（vitiligo）领域。"
    "你的任务是将英文医学论文摘要翻译并改写为通俗易懂的中文科普内容，面向普通患者。\n\n"
    "请严格遵守以下规则：\n"
    "1. 提取关键信息：治疗方法、研究结果、主要结论。\n"
    "2. 使用简单、非专业的语言，让没有医学背景的患者也能理解。\n"
    "3. 全部使用中文输出。\n"
    "4. 不要给出任何医疗建议。在摘要末尾附上免责声明："
    "\u201c以上内容仅供科普参考，不构成医疗建议。具体治疗方案请咨询专业医生。\u201d\n"
    "5. 保持客观，忠实于原文内容，不要添加原文中没有的信息。\n"
    "6. 输出格式：先用一句话总结核心发现，然后分段说明治疗方法、结果和结论。"
)

_USER_PROMPT_TEMPLATE = (
    "请将以下英文医学论文摘要改写为面向患者的中文科普摘要：\n\n{abstract}"
)

_RETRYABLE_ERRORS = (APIConnectionError, APITimeoutError, RateLimitError)

_MAX_RETRIES = 3
_INITIAL_BACKOFF = 1.0
_BACKOFF_MULTIPLIER = 2.0


class SummarizerError(Exception):
    """Raised when summarization fails after all retries."""


class Summarizer:
    """Generate patient-friendly Chinese summaries of medical paper abstracts.

    Supports both OpenAI and Volcengine (火山引擎) OpenAI-compatible API.
    When Volcengine API key is configured, it will be used automatically.

    The summarizer wraps the OpenAI ChatCompletion API and integrates
    rate-limiting and caching to operate within API quotas and avoid
    redundant work.

    Args:
        model: OpenAI model identifier (e.g. ``"gpt-3.5-turbo"``).
        api_key: OpenAI API key. Falls back to the ``OPENAI_API_KEY``
            environment variable when *None*.
        cache: Optional :class:`Cache` instance for storing summaries.
            When *None*, caching is disabled.
        rate_limiter: Optional :class:`RateLimiter` instance.  When *None*
            a default limiter of 10 requests per minute is used.
        cache_ttl: Time-to-live for cached summaries in seconds.
            Defaults to 30 days.
        max_retries: Maximum number of retries on transient errors.
        temperature: Sampling temperature for the model.

    Raises:
        ValueError: If no API key is provided or found in the environment.

    Example:
        >>> from src.utils.cache import Cache
        >>> cache = Cache("summaries.sqlite3")
        >>> summarizer = Summarizer(cache=cache)
        >>> summary = summarizer.summarize("JAK inhibitors showed ...")
    """

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        cache: Optional[Cache] = None,
        rate_limiter: Optional[RateLimiter] = None,
        cache_ttl: float = _DEFAULT_CACHE_TTL,
        max_retries: int = _MAX_RETRIES,
        temperature: float = 0.3,
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
            raise ValueError(
                "An API key is required. Provide it via the 'api_key' "
                "parameter or set VOLCENGINE_API_KEY in your environment."
            )

        self._client = OpenAI(api_key=resolved_key, base_url=resolved_base_url)
        self._model = resolved_model
        self._cache = cache
        self._rate_limiter = rate_limiter or RateLimiter(_DEFAULT_RATE_LIMIT)
        self._cache_ttl = cache_ttl
        self._max_retries = max_retries
        self._temperature = temperature

    @staticmethod
    def _cache_key(abstract: str) -> str:
        """Derive a deterministic cache key from the abstract text.

        Args:
            abstract: The source abstract.

        Returns:
            A hex-encoded SHA-256 hash prefixed with ``summary:``.
        """
        digest = hashlib.sha256(abstract.encode("utf-8")).hexdigest()
        return f"summary:{digest}"

    def _call_openai(self, abstract: str) -> str:
        """Send a single ChatCompletion request to OpenAI.

        Args:
            abstract: The English abstract to summarize.

        Returns:
            The model's response text.

        Raises:
            SummarizerError: If the response has no valid content.
        """
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": _USER_PROMPT_TEMPLATE.format(abstract=abstract),
                },
            ],
            temperature=self._temperature,
        )

        choice = response.choices[0] if response.choices else None
        if choice is None or choice.message.content is None:
            raise SummarizerError("OpenAI returned an empty response.")

        return choice.message.content.strip()

    def _call_with_retry(self, abstract: str) -> str:
        """Call OpenAI with exponential backoff on transient errors.

        Args:
            abstract: The English abstract to summarize.

        Returns:
            The model's response text.

        Raises:
            SummarizerError: If all retries are exhausted.
        """
        last_error: Exception | None = None
        backoff = _INITIAL_BACKOFF

        for attempt in range(1, self._max_retries + 1):
            try:
                return self._call_openai(abstract)
            except _RETRYABLE_ERRORS as exc:
                last_error = exc
                logger.warning(
                    "OpenAI transient error (attempt %d/%d): %s",
                    attempt,
                    self._max_retries,
                    exc,
                )
                if attempt < self._max_retries:
                    time.sleep(backoff)
                    backoff *= _BACKOFF_MULTIPLIER

        raise SummarizerError(
            f"Summarization failed after {self._max_retries} retries."
        ) from last_error

    def summarize(self, abstract: str) -> str:
        """Generate a patient-friendly Chinese summary of a medical abstract.

        The method first checks the cache for a previously generated summary.
        If no cached result is found it acquires a rate-limit token and calls
        the OpenAI API (with retry logic for transient errors).  The result is
        then stored in the cache before being returned.

        Args:
            abstract: An English-language medical paper abstract.

        Returns:
            A Chinese summary suitable for patients.

        Raises:
            ValueError: If *abstract* is empty or whitespace-only.
            SummarizerError: If the OpenAI API call fails after retries.

        Example:
            >>> summary = summarizer.summarize(
            ...     "This study evaluated the efficacy of ruxolitinib cream ..."
            ... )
        """
        if not abstract or not abstract.strip():
            raise ValueError("Abstract must not be empty.")

        abstract = abstract.strip()
        key = self._cache_key(abstract)

        if self._cache is not None:
            cached = self._cache.get(key)
            if cached is not None:
                logger.debug("Cache hit for key %s", key)
                return str(cached)

        self._rate_limiter.acquire()

        summary = self._call_with_retry(abstract)

        if self._cache is not None:
            self._cache.set(key, summary, ttl=self._cache_ttl)

        return summary
