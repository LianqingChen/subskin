"""OmicsDI API crawler for the SubSkin project.

Fetches vitiligo-related multi-omics datasets from the OmicsDI API
(https://www.omicsdi.org), which integrates genomics, proteomics,
and metabolomics datasets across repositories.

API: https://www.omicsdi.org/api/dataset/search
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import requests

from src.utils.cache import Cache
from src.utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

BASE_URL = "https://www.omicsdi.org/api/dataset/search"
DEFAULT_CACHE_TTL = 86400.0
DEFAULT_PAGE_SIZE = 20
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0


class OmicsDICrawler:
    """Crawler for fetching vitiligo omics datasets from OmicsDI.

    OmicsDI is a multi-omics data integration platform that aggregates
    datasets from major repositories (GEO, PRIDE, MetaboLights, etc.).

    Args:
        rate_limiter: Token-bucket rate limiter. Default 2 req/s.
        cache: SQLite-backed cache for API responses.
        cache_ttl: Cache time-to-live in seconds.
        timeout: HTTP request timeout.
    """

    def __init__(
        self,
        rate_limiter: Optional[RateLimiter] = None,
        cache: Optional[Cache] = None,
        cache_ttl: float = DEFAULT_CACHE_TTL,
        timeout: int = 30,
    ) -> None:
        self._limiter = rate_limiter or RateLimiter(requests_per_second=2.0)
        self._cache = cache or Cache()
        self._cache_ttl = cache_ttl
        self._timeout = timeout

    def search_datasets(
        self,
        query: str = "vitiligo",
        max_results: int = 200,
        page_size: int = DEFAULT_PAGE_SIZE,
    ) -> List[Dict[str, Any]]:
        """Search OmicsDI for vitiligo-related omics datasets.

        Args:
            query: Search term.
            max_results: Hard ceiling on results.
            page_size: Results per page.

        Returns:
            List of dataset dictionaries with fields: id, title, description,
            repository, accession, omics_type, url, pub_date, organisms.
        """
        results: List[Dict[str, Any]] = []
        start = 0

        while len(results) < max_results:
            batch = self._fetch_page(
                query=query, page_size=page_size, start=start
            )
            if not batch:
                break
            results.extend(batch)
            start += page_size
            if len(batch) < page_size:
                break

        return results[:max_results]

    def _fetch_page(
        self, query: str, page_size: int, start: int
    ) -> List[Dict[str, Any]]:
        cache_key = f"omicsdi:{query}:{start}:{page_size}"
        cached = self._cache.get(cache_key)
        if isinstance(cached, list):
            return cached

        datasets = self._request_api(
            query=query, page_size=page_size, start=start
        )
        parsed = [self._parse_dataset(ds) for ds in datasets]
        parsed = [p for p in parsed if p is not None]

        self._cache.set(cache_key, parsed, ttl=self._cache_ttl)
        return parsed

    def _request_api(
        self, query: str, page_size: int, start: int
    ) -> List[dict]:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                with self._limiter:
                    resp = requests.get(
                        BASE_URL,
                        params={
                            "query": query,
                            "size": page_size,
                            "start": start,
                        },
                        timeout=self._timeout,
                        headers={"Accept": "application/json"},
                    )
                    resp.raise_for_status()
                data = resp.json()
                return data.get("datasets", [])
            except requests.RequestException as e:
                logger.warning(
                    "OmicsDI API error (attempt %d/%d): %s",
                    attempt, MAX_RETRIES, e,
                )
                if attempt == MAX_RETRIES:
                    return []
                time.sleep(INITIAL_BACKOFF * (2 ** (attempt - 1)))
        return []

    def _parse_dataset(self, dataset: dict) -> Optional[Dict[str, Any]]:
        try:
            return {
                "id": dataset.get("id", ""),
                "title": dataset.get("title", ""),
                "description": dataset.get("description", "")[:2000],
                "repository": dataset.get("repository", ""),
                "accession": dataset.get("accession", ""),
                "omics_type": dataset.get("omicsType", ""),
                "url": dataset.get("url", ""),
                "pub_date": dataset.get("publicationDate", ""),
                "organisms": dataset.get("organisms", []),
                "source": "OmicsDI",
            }
        except Exception as e:
            logger.warning("Failed to parse OmicsDI dataset: %s", e)
            return None

    def get_vitiligo_genomics(self) -> List[Dict[str, Any]]:
        """Get vitiligo-related genomics/transcriptomics datasets."""
        return self.search_datasets(
            query="vitiligo AND (transcriptomics OR genomics OR proteomics)",
            max_results=100,
        )

    def get_vitiligo_proteomics(self) -> List[Dict[str, Any]]:
        """Get vitiligo-related proteomics datasets."""
        return self.search_datasets(
            query="vitiligo AND proteomics",
            max_results=50,
        )
