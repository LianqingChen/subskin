from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from importlib import import_module
from typing import Any

from src.models.paper import Paper, PaperSource
from src.utils.cache import Cache
from src.utils.rate_limiter import RateLimiter

try:
    _metapub = import_module("metapub")
    PubMedFetcher = getattr(_metapub, "PubMedFetcher", None)
except ImportError:
    PubMedFetcher = None

logger = logging.getLogger(__name__)


class PubMedCrawler:
    """Crawler for PubMed papers related to vitiligo.

    The crawler uses metapub's ``PubMedFetcher`` over PubMed E-utilities and
    integrates project-level caching and rate limiting utilities.

    Args:
        query: PubMed query string. Defaults to ``"vitiligo[MeSH Terms]"``.
        requests_per_second: PubMed free-tier request rate limit.
        page_size: Number of PMIDs to fetch per page.
        max_results: Hard ceiling for total number of records to fetch.
        cache: Optional cache instance. If omitted, an in-memory cache is used.
        cache_ttl_seconds: TTL for cached API responses.
        max_retries: Number of retry attempts for transient failures.
        backoff_base_seconds: Base delay for exponential backoff.
        fetcher: Optional preconfigured metapub fetcher for dependency injection.
    """

    DEFAULT_QUERY = "vitiligo[MeSH Terms]"
    DEFAULT_CACHE_TTL_SECONDS = 60 * 60 * 24
    DEFAULT_PAGE_SIZE = 250
    DEFAULT_MAX_RESULTS = 10_000

    def __init__(
        self,
        *,
        query: str = DEFAULT_QUERY,
        requests_per_second: float = 3.0,
        page_size: int = DEFAULT_PAGE_SIZE,
        max_results: int = DEFAULT_MAX_RESULTS,
        cache: Cache | None = None,
        cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
        max_retries: int = 3,
        backoff_base_seconds: float = 1.0,
        fetcher: Any | None = None,
    ) -> None:
        if page_size <= 0:
            raise ValueError("page_size must be positive")
        if max_results <= 0:
            raise ValueError("max_results must be positive")
        if max_retries <= 0:
            raise ValueError("max_retries must be positive")
        if backoff_base_seconds <= 0:
            raise ValueError("backoff_base_seconds must be positive")

        if fetcher is None:
            if PubMedFetcher is None:
                raise RuntimeError(
                    "metapub is not installed. Install dependencies before using "
                    "PubMedCrawler."
                )
            fetcher = PubMedFetcher()

        self._query = query
        self._limiter = RateLimiter(requests_per_second=requests_per_second)
        self._page_size = page_size
        self._max_results = max_results
        self._cache = cache or Cache()
        self._cache_ttl_seconds = cache_ttl_seconds
        self._max_retries = max_retries
        self._backoff_base_seconds = backoff_base_seconds
        self._fetcher = fetcher

    def search_papers(self, query: str | None = None) -> list[Paper]:
        """Search PubMed and return normalized paper objects.

        Args:
            query: Optional query override. If omitted, the crawler default query
                is used (MeSH term search for vitiligo).

        Returns:
            List of ``Paper`` objects.
        """
        effective_query = query or self._query
        pmids = self._search_pmids_with_pagination(effective_query)

        papers: list[Paper] = []
        for pmid in pmids:
            try:
                paper = self._fetch_paper_by_pmid(pmid)
                if paper is not None:
                    papers.append(paper)
            except Exception as e:
                logger.warning("Skipping PMID=%s due to error: %s", pmid, str(e))
                continue

        return papers

    def _search_pmids_with_pagination(self, query: str) -> list[str]:
        all_pmids: list[str] = []
        retstart = 0

        while retstart < self._max_results:
            page_pmids = self._fetch_pmids_page(query=query, retstart=retstart)
            if not page_pmids:
                break

            all_pmids.extend(page_pmids)
            retstart += self._page_size

            if len(page_pmids) < self._page_size:
                break

        return all_pmids[: self._max_results]

    def _fetch_pmids_page(self, *, query: str, retstart: int) -> list[str]:
        cache_key = f"pubmed:search:{query}:{retstart}:{self._page_size}"
        cached = self._cache.get(cache_key)
        if isinstance(cached, list):
            return [str(item) for item in cached]

        pmids = self._with_retries(
            lambda: self._call_with_rate_limit(
                self._fetcher.pmids_for_query,
                query,
                retstart=retstart,
                retmax=self._page_size,
            )
        )

        normalized_pmids = [str(pmid) for pmid in pmids]
        self._cache.set(cache_key, normalized_pmids, ttl=self._cache_ttl_seconds)
        return normalized_pmids

    def _fetch_paper_by_pmid(self, pmid: str) -> Paper | None:
        cache_key = f"pubmed:article:{pmid}"
        cached = self._cache.get(cache_key)
        if isinstance(cached, dict):
            try:
                return Paper(**cached)
            except Exception:
                logger.warning("Invalid cached paper payload for PMID=%s", pmid)

        article = self._with_retries(
            lambda: self._call_with_rate_limit(self._fetcher.article_by_pmid, pmid)
        )

        if article is None:
            return None

        paper = self._article_to_paper(article, pmid)
        if paper is None:
            return None

        self._cache.set(
            cache_key,
            self._paper_to_cache_payload(paper),
            ttl=self._cache_ttl_seconds,
        )
        return paper

    def _article_to_paper(self, article: Any, pmid: str) -> Paper | None:
        title_raw = getattr(article, "title", "")
        title = str(title_raw).strip()
        if not title:
            logger.warning("Skipping PMID=%s because title is empty", pmid)
            return None

        authors = self._normalize_authors(getattr(article, "authors", []))
        mesh_terms = self._normalize_str_list(
            self._first_non_none(
                getattr(article, "mesh_terms", None),
                getattr(article, "mesh", None),
                getattr(article, "meshheadings", None),
            )
        )
        keywords = self._normalize_str_list(getattr(article, "keywords", None))

        pub_date_raw = self._first_non_none(
            getattr(article, "pubdate", None),
            getattr(article, "publication_date", None),
            getattr(article, "year", None),
        )
        pub_date = str(pub_date_raw).strip() if pub_date_raw is not None else None

        return Paper(
            pmid=str(getattr(article, "pmid", pmid) or pmid),
            doi=self._safe_optional_str(getattr(article, "doi", None)),
            title=title,
            abstract=self._safe_optional_str(getattr(article, "abstract", None)),
            authors=authors,
            journal=self._safe_optional_str(getattr(article, "journal", None)),
            pub_date=pub_date,
            mesh_terms=mesh_terms,
            keywords=keywords,
            source=PaperSource.PUBMED,
            crawled_at=datetime.now(timezone.utc),
            url=None,
            citation_count=None,
            language="en",
            translated=False,
            summarized=False,
        )

    @staticmethod
    def _paper_to_cache_payload(paper: Paper) -> dict[str, Any]:
        payload: dict[str, Any] = paper.model_dump()
        payload["crawled_at"] = paper.crawled_at.isoformat()
        return payload

    @staticmethod
    def _safe_optional_str(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _first_non_none(*values: Any) -> Any:
        for value in values:
            if value is not None:
                return value
        return None

    @staticmethod
    def _normalize_authors(authors: Any) -> list[str]:
        if authors is None:
            return []

        normalized: list[str] = []
        for author in authors:
            author_text = str(author).strip()
            if author_text:
                normalized.append(author_text)
        return normalized

    @staticmethod
    def _normalize_str_list(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            text = value.strip()
            return [text] if text else []

        try:
            result: list[str] = []
            for item in value:
                item_text = str(item).strip()
                if item_text:
                    result.append(item_text)
            return result
        except TypeError:
            text = str(value).strip()
            return [text] if text else []

    def _call_with_rate_limit(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        with self._limiter:
            return func(*args, **kwargs)

    def _with_retries(self, operation: Any) -> Any:
        last_error: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                return operation()
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if not self._is_transient_error(exc) or attempt == self._max_retries:
                    raise

                sleep_seconds = self._backoff_base_seconds * (2 ** (attempt - 1))
                logger.warning(
                    "Transient PubMed error on attempt %s/%s: %s. Retrying in %.2fs",
                    attempt,
                    self._max_retries,
                    exc,
                    sleep_seconds,
                )
                time.sleep(sleep_seconds)

        if last_error is not None:
            raise last_error
        raise RuntimeError("Unexpected retry state")

    @staticmethod
    def _is_transient_error(exc: Exception) -> bool:
        response = getattr(exc, "response", None)
        status_code = getattr(response, "status_code", None)
        if isinstance(status_code, int) and 500 <= status_code < 600:
            return True

        message = str(exc).lower()
        transient_markers = (
            "timeout",
            "timed out",
            "temporarily unavailable",
            "connection reset",
            "connection aborted",
            "connection error",
            "server error",
            "502",
            "503",
            "504",
        )
        return any(marker in message for marker in transient_markers)
