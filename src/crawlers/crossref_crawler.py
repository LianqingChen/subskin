"""CrossRef API crawler for the SubSkin project.

Fetches vitiligo-related paper metadata from the CrossRef API
(DOI registry) with rate limiting, caching, and retry support.

CrossRef is a free, open API — no API key required.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, List, Optional

import requests

from src.models.paper import Paper, PaperSource
from src.utils.cache import Cache
from src.utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

BASE_URL = "https://api.crossref.org/works"
DEFAULT_ROWS = 100
DEFAULT_CACHE_TTL = 86400.0
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0


class CrossRefCrawler:
    """Crawler for fetching vitiligo paper metadata from the CrossRef API.

    CrossRef is the global DOI registration agency. Its free API returns
    structured metadata for academic papers indexed by DOI.

    Args:
        rate_limiter: Token-bucket rate limiter. Default 50 req/s
            (CrossRef allows up to 50 req/s without a token).
        cache: SQLite-backed cache for API responses.
        cache_ttl: Cache time-to-live in seconds.
        max_retries: Retry attempts on transient errors.
        timeout: HTTP request timeout in seconds.
    """

    def __init__(
        self,
        rate_limiter: Optional[RateLimiter] = None,
        cache: Optional[Cache] = None,
        cache_ttl: float = DEFAULT_CACHE_TTL,
        max_retries: int = MAX_RETRIES,
        timeout: int = 15,
    ) -> None:
        self._limiter = rate_limiter or RateLimiter(requests_per_second=50.0)
        self._cache = cache or Cache()
        self._cache_ttl = cache_ttl
        self._max_retries = max_retries
        self._timeout = timeout

    def search(
        self,
        query: str = "vitiligo",
        max_results: int = 500,
        rows: int = DEFAULT_ROWS,
    ) -> List[Paper]:
        """Search CrossRef for vitiligo-related papers.

        Args:
            query: Search query. Defaults to "vitiligo".
            max_results: Hard ceiling on results.
            rows: Results per API page (max 1000).

        Returns:
            List of ``Paper`` objects.
        """
        papers: List[Paper] = []
        offset = 0

        while len(papers) < max_results:
            batch = self._fetch_page(query=query, rows=rows, offset=offset)
            if not batch:
                break
            papers.extend(batch)
            offset += rows
            if len(batch) < rows:
                break

        return papers[:max_results]

    def _fetch_page(
        self, query: str, rows: int, offset: int
    ) -> List[Paper]:
        cache_key = f"crossref:{query}:{offset}:{rows}"
        cached = self._cache.get(cache_key)
        if isinstance(cached, list):
            papers: List[Paper] = []
            for item in cached:
                try:
                    papers.append(Paper(**item))
                except Exception:
                    continue
            return papers

        items = self._request_api(query=query, rows=rows, offset=offset)
        papers = [self._parse_item(item) for item in items]
        papers = [p for p in papers if p is not None]

        cache_payload = [
            {
                "title": p.title,
                "abstract": p.abstract,
                "authors": p.authors,
                "doi": p.doi,
                "journal": p.journal,
                "pub_date": p.pub_date,
                "source": p.source.value,
                "url": p.url,
            }
            for p in papers
        ]
        self._cache.set(cache_key, cache_payload, ttl=self._cache_ttl)
        return papers

    def _request_api(self, query: str, rows: int, offset: int) -> List[dict]:
        for attempt in range(1, self._max_retries + 1):
            try:
                with self._limiter:
                    resp = requests.get(
                        BASE_URL,
                        params={
                            "query": query,
                            "rows": rows,
                            "offset": offset,
                            "filter": "type:journal-article",
                            "sort": "relevance",
                        },
                        timeout=self._timeout,
                    )
                    resp.raise_for_status()
                data = resp.json()
                items = data.get("message", {}).get("items", [])
                return items
            except requests.RequestException as e:
                logger.warning(
                    "CrossRef API error (attempt %d/%d): %s",
                    attempt, self._max_retries, e,
                )
                if attempt == self._max_retries:
                    return []
                time.sleep(INITIAL_BACKOFF * (2 ** (attempt - 1)))
        return []

    def _parse_item(self, item: dict) -> Optional[Paper]:
        title_list = item.get("title", [])
        title = title_list[0] if title_list else None
        if not title:
            return None

        authors: List[str] = []
        for author_data in item.get("author", []):
            given = author_data.get("given", "")
            family = author_data.get("family", "")
            name = f"{given} {family}".strip()
            if name:
                authors.append(name)

        abstract_text = item.get("abstract", "")
        if isinstance(abstract_text, str) and abstract_text.strip().startswith("<"):
            import re
            abstract_text = re.sub(r"<[^>]+>", "", abstract_text)

        doi = item.get("DOI")
        url = f"https://doi.org/{doi}" if doi else None

        container = item.get("container-title", [])
        journal = container[0] if container else None

        pub_date = None
        pub_date_parts = item.get("published", {}).get("date-parts", [[]])
        if pub_date_parts and pub_date_parts[0]:
            parts = pub_date_parts[0]
            pub_date = str(parts[0])
            if len(parts) >= 2:
                pub_date += f"-{int(parts[1]):02d}"
            if len(parts) >= 3:
                pub_date += f"-{int(parts[2]):02d}"

        try:
            return Paper(
                title=title,
                abstract=abstract_text.strip() if abstract_text else None,
                authors=authors,
                doi=doi,
                journal=journal,
                pub_date=pub_date,
                source=PaperSource.OTHER,
                url=url,
            )
        except Exception as e:
            logger.warning("Failed to create Paper from CrossRef item: %s", e)
            return None
