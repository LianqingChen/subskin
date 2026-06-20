"""Medical encyclopedia and patient education crawler.

Scrapes vitiligo-related content from:
  - 默沙东诊疗手册 (msdmanuals.cn) — medical encyclopedia
  - 丁香园用药参考 (drugs.dxy.cn) — drug information
  - Dove Medical Press (dovepress.com) — open-access reviews
  - Broad Institute (broadinstitute.org) — immunology research
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

from src.utils.cache import Cache
from src.utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
INITIAL_BACKOFF = 1.5
DEFAULT_CACHE_TTL = 86400.0

SITES = [
    {
        "id": "msd_manual",
        "name": "默沙东诊疗手册",
        "base_url": "https://www.msdmanuals.cn",
        "search_url": "https://www.msdmanuals.cn/search",
        "search_param": "q",
        "search_term": "白癜风",
        "title_sel": "h1, h2, .search-result-title",
        "content_sel": ".topic-content, .search-result-snippet",
        "result_sel": ".search-result-item, .result-item, li",
        "source_tier": "D",
        "authority_weight": 0.5,
        "enabled": False,
    },
    {
        "id": "dxy_drugs",
        "name": "丁香园用药参考",
        "base_url": "https://drugs.dxy.cn",
        "search_url": "https://drugs.dxy.cn/index/search",
        "search_param": "keyword",
        "search_term": "白癜风",
        "title_sel": "h1, .drug-name",
        "content_sel": ".drug-detail, .detail-content",
        "result_sel": ".search-list li, .result-item",
        "source_tier": "D",
        "authority_weight": 0.5,
        "enabled": False,
    },
    {
        "id": "dove_medical",
        "name": "Dove Medical Press",
        "base_url": "https://www.dovepress.com",
        "search_url": "https://www.dovepress.com/search?q=vitiligo",
        "search_param": None,
        "search_term": "",
        "title_sel": "h1, .article-title, h4",
        "content_sel": ".article-body, .abstract, .teaser",
        "result_sel": ".search-result, .article-listing, .views-row",
        "source_tier": "C",
        "authority_weight": 0.8,
        "enabled": False,
    },
    {
        "id": "broad_institute",
        "name": "Broad Institute",
        "base_url": "https://www.broadinstitute.org",
        "search_url": "https://www.broadinstitute.org/search",
        "search_param": "search",
        "search_term": "vitiligo",
        "title_sel": "h1, .page-title, h2",
        "content_sel": ".main-content, article, .field-content",
        "result_sel": ".search-result, .views-row, .teaser-item",
        "source_tier": "A",
        "authority_weight": 1.2,
        "enabled": True,
    },
    {
        "id": "haodf",
        "name": "好大夫在线",
        "base_url": "https://www.haodf.com",
        "search_url": "https://www.haodf.com/jibing/baidianfeng/list",
        "search_param": None,
        "search_term": "",
        "title_sel": "h1, .article-title, h2",
        "content_sel": ".article-content, .detail-content, p",
        "result_sel": ".article-item, .news-item, .list-item",
        "source_tier": "D",
        "authority_weight": 0.5,
        "enabled": True,
    },
    {
        "id": "avrf",
        "name": "American Vitiligo Research Foundation",
        "base_url": "https://www.avrf.org",
        "search_url": "https://www.avrf.org/page/search",
        "search_param": "q",
        "search_term": "vitiligo",
        "title_sel": "h1, h2, .title",
        "content_sel": ".content, article, .entry-summary",
        "result_sel": ".search-result, article, .post-item",
        "source_tier": "C",
        "authority_weight": 0.8,
        "enabled": True,
    },
]


class MedicalContentCrawler:
    """Unified crawler for medical encyclopedia and patient education sites.

    Handles multiple sites with similar scraping patterns.
    Each site config defines its selectors independently.

    Args:
        rate_limiter: Rate limiter for polite crawling.
        cache: Cache for scraped content.
        cache_ttl: Cache TTL in seconds.
        timeout: HTTP request timeout.
    """

    def __init__(
        self,
        rate_limiter: Optional[RateLimiter] = None,
        cache: Optional[Cache] = None,
        cache_ttl: float = DEFAULT_CACHE_TTL,
        timeout: int = 20,
    ) -> None:
        self._limiter = rate_limiter or RateLimiter(requests_per_second=1.0)
        self._cache = cache or Cache()
        self._cache_ttl = cache_ttl
        self._timeout = timeout

    def crawl_all(self) -> List[Dict[str, Any]]:
        """Crawl all configured sites that are enabled."""
        articles: List[Dict[str, Any]] = []
        for site in SITES:
            if not site.get("enabled", True):
                logger.info("Skipping disabled site: %s", site["name"])
                continue
            try:
                site_articles = self._crawl_site(site)
                articles.extend(site_articles)
                logger.info("%s: %d articles", site["name"], len(site_articles))
            except Exception as e:
                logger.error("Failed %s: %s", site["name"], e)
        return articles

    def crawl_site(self, site_id: str) -> List[Dict[str, Any]]:
        """Crawl a specific site by ID."""
        for site in SITES:
            if site["id"] == site_id:
                return self._crawl_site(site)
        return []

    def _crawl_site(self, site: dict) -> List[Dict[str, Any]]:
        cache_key = f"medical:{site['id']}:{site['search_term']}"
        cached = self._cache.get(cache_key)
        if isinstance(cached, list):
            return cached

        if site.get("search_param"):
            params = {site["search_param"]: site["search_term"]}
            html = self._fetch_html(site["search_url"], params)
        else:
            html = self._fetch_html(site["search_url"])

        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        articles = self._parse_results(soup, site)
        self._cache.set(cache_key, articles, ttl=self._cache_ttl)
        return articles

    def _fetch_html(
        self, url: str, params: Optional[dict] = None
    ) -> Optional[str]:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (compatible; SubSkin/2.0; "
                "+https://subskin.example.com) "
                "Python-requests/2.x"
            )
        }
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                with self._limiter:
                    kwargs = {"url": url, "headers": headers, "timeout": self._timeout}
                    if params:
                        kwargs["params"] = params
                    resp = requests.get(**kwargs)
                    if resp.status_code in (403, 404):
                        logger.warning("%s returned %d", url, resp.status_code)
                        return None
                    resp.raise_for_status()
                return resp.text
            except requests.RequestException as e:
                logger.warning(
                    "%s (attempt %d/%d): %s",
                    url, attempt, MAX_RETRIES, e,
                )
                if attempt == MAX_RETRIES:
                    return None
                time.sleep(INITIAL_BACKOFF * (2 ** (attempt - 1)))
        return None

    def _parse_results(
        self, soup: BeautifulSoup, site: dict
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        result_sel = site.get("result_sel", ".search-result")
        elements = soup.select(result_sel)

        for el in elements:
            title = ""
            for sel in site["title_sel"].split(","):
                found = el.select_one(sel.strip())
                if found:
                    title = found.get_text(strip=True)
                    if title:
                        break

            if not title or len(title) < 4:
                continue

            content = ""
            for sel in site["content_sel"].split(","):
                found = el.select_one(sel.strip())
                if found:
                    content = found.get_text(separator=" ", strip=True)
                    if content:
                        break

            link = ""
            a_el = el.select_one("a")
            if a_el and a_el.get("href"):
                href = a_el["href"]
                if href.startswith("/"):
                    link = site["base_url"].rstrip("/") + href
                elif href.startswith("http"):
                    link = href

            results.append({
                "source_id": site["id"],
                "source_name": site["name"],
                "title": title[:500],
                "content": content[:3000],
                "url": link or site["base_url"],
                "source_tier": site["source_tier"],
                "authority_weight": site["authority_weight"],
                "category": "medical_education"
                if site["id"] in ("msd_manual", "haodf", "avrf")
                else "drug_info"
                if site["id"] == "dxy_drugs"
                else "research_review",
                "pub_date": "",
            })

        return results[:30]
