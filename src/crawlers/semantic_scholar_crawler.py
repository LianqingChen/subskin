"""Semantic Scholar paper crawler for the SubSkin project.

Fetches vitiligo-related papers from the Semantic Scholar Academic Graph API
with rate limiting, caching, and exponential-backoff retry on transient errors.
"""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime
from typing import Any

import requests

from src.models.paper import Paper, PaperSource
from src.utils.cache import Cache
from src.utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

BASE_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
DEFAULT_FIELDS = (
    "paperId,title,abstract,authors,venue,year,"
    "citationCount,url,externalIds,publicationDate"
)
DEFAULT_PAGE_LIMIT = 100
DEFAULT_CACHE_TTL = 86400.0
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0


class SemanticScholarCrawler:
    """Crawler for fetching vitiligo papers from the Semantic Scholar API.

    Uses the Semantic Scholar Academic Graph API to search for papers.
    Integrates rate limiting, caching, and exponential-backoff retry
    for transient failures.

    Args:
        rate_limiter: Token-bucket rate limiter. Defaults to 1000 req/s.
        cache: SQLite-backed cache for API responses.
        cache_ttl: Time-to-live for cached entries in seconds.
        max_retries: Maximum retry attempts on transient errors.
        timeout: HTTP request timeout in seconds.

    Example:
        >>> with SemanticScholarCrawler() as crawler:
        ...     papers = crawler.search("vitiligo treatment", max_results=50)
    """

    def __init__(
        self,
        rate_limiter: RateLimiter | None = None,
        cache: Cache | None = None,
        cache_ttl: float = DEFAULT_CACHE_TTL,
        max_retries: int = MAX_RETRIES,
        timeout: int = 30,
    ) -> None:
        self._rate_limiter = rate_limiter or RateLimiter(1000)
        self._cache = cache or Cache()
        self._owns_cache = cache is None
        self._cache_ttl = cache_ttl
        self._max_retries = max_retries
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "SubSkin/0.1.0 (vitiligo knowledge base)",
            }
        )

    def _backoff_sleep(self, seconds: float) -> None:
        time.sleep(seconds)

    @staticmethod
    def _cache_key(query: str, offset: int, limit: int) -> str:
        """Generate a deterministic cache key from query parameters.

        Args:
            query: Search query string.
            offset: Pagination offset.
            limit: Results per page.

        Returns:
            Hex-encoded SHA-256 digest.
        """
        raw = f"semantic_scholar:{query}:{offset}:{limit}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _make_request(self, params: dict[str, Any]) -> dict[str, Any]:
        """Send a rate-limited GET request with exponential-backoff retry.

        Retries on HTTP 5xx, timeouts, and connection errors.  Client
        errors (4xx) are raised immediately.

        Args:
            params: Query parameters forwarded to the API.

        Returns:
            Parsed JSON response body.

        Raises:
            requests.HTTPError: On non-retryable HTTP errors or after
                exhausting all retry attempts.
            requests.Timeout: After exhausting all retry attempts.
            requests.ConnectionError: After exhausting all retry attempts.
        """
        backoff = INITIAL_BACKOFF
        last_exception: Exception | None = None

        for attempt in range(self._max_retries):
            with self._rate_limiter:
                try:
                    response = self._session.get(
                        BASE_URL,
                        params=params,
                        timeout=self._timeout,
                    )
                    response.raise_for_status()
                    data: dict[str, Any] = response.json()
                    return data
                except requests.Timeout as exc:
                    last_exception = exc
                    logger.warning(
                        "Request timed out (attempt %d/%d)",
                        attempt + 1,
                        self._max_retries,
                    )
                except requests.HTTPError as exc:
                    last_exception = exc
                    status = (
                        exc.response.status_code
                        if exc.response is not None
                        else 0
                    )
                    if status < 500:
                        raise
                    logger.warning(
                        "Server error %d (attempt %d/%d)",
                        status,
                        attempt + 1,
                        self._max_retries,
                    )
                except requests.ConnectionError as exc:
                    last_exception = exc
                    logger.warning(
                        "Connection error (attempt %d/%d)",
                        attempt + 1,
                        self._max_retries,
                    )

            if attempt < self._max_retries - 1:
                self._backoff_sleep(backoff)
                backoff *= 2

        assert last_exception is not None
        raise last_exception

    def _fetch_page(
        self, query: str, offset: int, limit: int
    ) -> dict[str, Any]:
        """Fetch a single page of search results, using cache when available.

        Args:
            query: Search query string.
            offset: Pagination offset.
            limit: Results per page.

        Returns:
            API response (from network or cache).
        """
        key = self._cache_key(query, offset, limit)
        cached = self._cache.get(key)
        if cached is not None:
            logger.debug("Cache hit for query=%r offset=%d", query, offset)
            result: dict[str, Any] = cached
            return result

        params: dict[str, Any] = {
            "query": query,
            "offset": offset,
            "limit": limit,
            "fields": DEFAULT_FIELDS,
        }
        data = self._make_request(params)
        self._cache.set(key, data, ttl=self._cache_ttl)
        return data

    @staticmethod
    def _parse_paper(raw: dict[str, Any]) -> Paper:
        """Convert a raw API record into a :class:`Paper`.

        Args:
            raw: Single paper object from the API ``data`` array.

        Returns:
            Populated :class:`Paper` instance.
        """
        external_ids: dict[str, str] = raw.get("externalIds") or {}
        doi: str | None = external_ids.get("DOI")

        authors_raw: list[dict[str, Any]] = raw.get("authors") or []
        authors = [a["name"] for a in authors_raw if isinstance(a, dict) and "name" in a]

        url: str | None = raw.get("url")
        if not url:
            paper_id = raw.get("paperId")
            if paper_id:
                url = f"https://www.semanticscholar.org/paper/{paper_id}"

        pub_date: str | None = raw.get("publicationDate")
        if not pub_date and raw.get("year") is not None:
            pub_date = str(raw["year"])

        return Paper(
            doi=doi,
            title=raw.get("title") or "Untitled",
            abstract=raw.get("abstract"),
            authors=authors,
            journal=raw.get("venue") or None,
            pub_date=pub_date,
            source=PaperSource.SEMANTIC_SCHOLAR,
            url=url,
            citation_count=raw.get("citationCount"),
            crawled_at=datetime.now(),
        )

    def search(
        self,
        query: str,
        max_results: int = 100,
        offset: int = 0,
    ) -> list[Paper]:
        """Search Semantic Scholar for papers matching *query*.

        Automatically paginates through results until *max_results* papers
        have been collected or no more results are available.

        Args:
            query: Free-text search string (e.g. ``"vitiligo treatment"``).
            max_results: Upper bound on the number of papers returned.
            offset: Starting pagination offset.

        Returns:
            List of :class:`Paper` objects.

        Raises:
            ValueError: If *query* is empty.
            requests.HTTPError: On non-retryable API errors.
        """
        if not query or not query.strip():
            raise ValueError("Search query must not be empty")

        papers: list[Paper] = []
        current_offset = offset

        while len(papers) < max_results:
            page_limit = min(DEFAULT_PAGE_LIMIT, max_results - len(papers))
            data = self._fetch_page(query, current_offset, page_limit)

            results: list[dict[str, Any]] = data.get("data") or []
            if not results:
                break

            for raw_paper in results:
                try:
                    papers.append(self._parse_paper(raw_paper))
                except Exception:
                    logger.warning(
                        "Failed to parse paper %s",
                        raw_paper.get("paperId", "unknown"),
                        exc_info=True,
                    )

            total: int = data.get("total", 0)
            current_offset += len(results)
            if current_offset >= total:
                break

        logger.info("Search for %r returned %d papers", query, len(papers))
        return papers

    def close(self) -> None:
        """Release HTTP session and internally-created cache resources."""
        self._session.close()
        if self._owns_cache:
            self._cache.close()

    def __enter__(self) -> SemanticScholarCrawler:
        """Return the crawler instance for context-manager usage."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object | None,
    ) -> None:
        """Close resources when leaving the context manager."""
        self.close()
