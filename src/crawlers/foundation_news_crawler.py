"""Foundation news crawler for the SubSkin project.

Crawls vitiligo research foundation websites and clinical trial news
outlets for the latest research developments, regulatory updates, and
awareness initiatives.

Targets:
  - VR Foundation (vrfoundation.org)
  - Global Vitiligo Foundation (globalvitiligofoundation.org)
  - Clinical Trial Vanguard (clinicaltrialvanguard.com)
  - 生物通 (ebiotrade.com)
  - 生物谷 (bioon.com)
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from typing import Any, List, Optional

import requests
from bs4 import BeautifulSoup

from src.models.paper import Paper, PaperSource
from src.utils.cache import Cache
from src.utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
INITIAL_BACKOFF = 1.5
DEFAULT_CACHE_TTL = 3600.0

FOUNDATION_SITES = [
    {
        "id": "vr_foundation",
        "name": "VR Foundation",
        "base_url": "https://vrfoundation.org",
        "article_selectors": ["article", ".post", ".news-item", ".blog-entry"],
        "title_selectors": ["h1", "h2", "h3", ".entry-title", ".post-title"],
        "content_selectors": [
            ".entry-content", ".post-content", "article p",
            ".content", "main",
        ],
        "search_path": "/?s=vitiligo",
    },
    {
        "id": "gvf",
        "name": "Global Vitiligo Foundation",
        "base_url": "https://globalvitiligofoundation.org",
        "article_selectors": ["article", ".post", ".news-item", ".blog-entry"],
        "title_selectors": ["h1", "h2", "h3", ".entry-title"],
        "content_selectors": [".entry-content", ".post-content", "main"],
        "search_path": "/?s=vitiligo",
    },
    {
        "id": "clinical_trial_vanguard",
        "name": "Clinical Trial Vanguard",
        "base_url": "https://www.clinicaltrialvanguard.com",
        "article_selectors": ["article", ".post", ".news-item"],
        "title_selectors": ["h1", "h2", ".entry-title", ".post-title"],
        "content_selectors": [".entry-content", ".post-content", "article p"],
        "search_path": "/?s=vitiligo",
    },
]

CHINESE_NEWS_SITES = [
    {
        "id": "ebiotrade",
        "name": "生物通",
        "base_url": "https://www.ebiotrade.com",
        "search_url": "https://www.ebiotrade.com/newsf/search-result.asp",
        "search_param": "keyword",
        "title_selectors": ["h1", "h2", "h3"],
        "content_selectors": [".content", "#content", "article"],
    },
    {
        "id": "bioon",
        "name": "生物谷",
        "base_url": "https://www.bioon.com",
        "search_url": "https://www.bioon.com/search/",
        "search_param": "q",
        "title_selectors": ["h1", "h2", ".article-title"],
        "content_selectors": [".article-content", "#content", "article"],
    },
]


class FoundationNewsCrawler:
    """Crawler for foundation news and clinical trial media.

    Scrapes vitiligo-related news, research updates, and regulatory
    announcements from foundation websites and industry media outlets.

    Args:
        rate_limiter: Token-bucket rate limiter for polite crawling.
        cache: SQLite-backed cache for scraped content.
        cache_ttl: Cache time-to-live in seconds.
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

    def crawl_all(self) -> List[dict]:
        """Crawl all configured foundation and news sites.

        Returns:
            List of article dicts with keys: source_id, source_name, title,
            content, url, pub_date, category.
        """
        articles: List[dict] = []

        for site in FOUNDATION_SITES:
            try:
                site_articles = self._crawl_foundation(site)
                articles.extend(site_articles)
                logger.info(
                    "Crawled %s: %d articles", site["name"], len(site_articles)
                )
            except Exception as e:
                logger.error("Failed to crawl %s: %s", site["name"], e)

        for site in CHINESE_NEWS_SITES:
            try:
                site_articles = self._crawl_chinese_news(site)
                articles.extend(site_articles)
                logger.info(
                    "Crawled %s: %d articles", site["name"], len(site_articles)
                )
            except Exception as e:
                logger.error("Failed to crawl %s: %s", site["name"], e)

        return articles

    def _crawl_foundation(self, site: dict) -> List[dict]:
        base_url = site["base_url"]
        search_path = site.get("search_path", "/?s=vitiligo")
        search_url = base_url + search_path

        cache_key = f"foundation:{site['id']}:index"
        cached = self._cache.get(cache_key)
        if isinstance(cached, list):
            return cached

        html = self._fetch_html(search_url)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        articles = self._extract_articles(soup, site)
        self._cache.set(cache_key, articles, ttl=self._cache_ttl)
        return articles

    def _crawl_chinese_news(self, site: dict) -> List[dict]:
        cache_key = f"foundation:{site['id']}:vitiligo"
        cached = self._cache.get(cache_key)
        if isinstance(cached, list):
            return cached

        search_url = site["search_url"]
        param = site["search_param"]

        html = self._fetch_html(
            search_url, params={param: "白癜风"}
        )
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        articles = self._extract_articles(soup, site)
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
                    resp = requests.get(
                        url,
                        params=params,
                        headers=headers,
                        timeout=self._timeout,
                    )
                    if resp.status_code in (403, 404):
                        logger.warning(
                            "%s returned %d", url, resp.status_code
                        )
                        return None
                    resp.raise_for_status()
                return resp.text
            except requests.RequestException as e:
                logger.warning(
                    "HTTP error on %s (attempt %d/%d): %s",
                    url, attempt, MAX_RETRIES, e,
                )
                if attempt == MAX_RETRIES:
                    return None
                time.sleep(INITIAL_BACKOFF * (2 ** (attempt - 1)))
        return None

    def _extract_articles(
        self, soup: BeautifulSoup, site: dict
    ) -> List[dict]:
        articles: List[dict] = []
        selectors = site.get("article_selectors", ["article"])

        for selector in selectors:
            elements = soup.select(selector)
            for el in elements:
                title = self._extract_text(el, site.get("title_selectors", ["h1", "h2"]))
                if not title:
                    continue
                if not self._is_vitiligo_related(title):
                    continue

                content = self._extract_text(
                    el, site.get("content_selectors", ["p"])
                )
                link = self._extract_link(el, site["base_url"])

                articles.append({
                    "source_id": site["id"],
                    "source_name": site["name"],
                    "title": title[:500],
                    "content": content[:2000],
                    "url": link,
                    "pub_date": "",
                    "category": "research_news",
                })

        return articles[:50]

    @staticmethod
    def _extract_text(el, selectors: List[str]) -> str:
        for sel in selectors:
            found = el.select_one(sel)
            if found:
                text = found.get_text(separator=" ", strip=True)
                if text:
                    return text
        return ""

    @staticmethod
    def _extract_link(el, base_url: str) -> str:
        link = el.select_one("a")
        if link and link.get("href"):
            href = link["href"]
            if href.startswith("/"):
                return base_url.rstrip("/") + href
            if href.startswith("http"):
                return href
        return base_url

    @staticmethod
    def _is_vitiligo_related(text: str) -> bool:
        keywords = [
            "vitiligo", "白癜风", "白斑", "色素脱失",
            "JAK inhibitor", "JAK抑制剂",
            "ruxolitinib", "鲁索利替尼", "Opzelura",
            "upadacitinib", "afamelanotide",
            "melanocyte", "黑素细胞", "repigmentation", "复色",
            "autoimmune skin", "自身免疫性皮肤病",
        ]
        text_lower = text.lower()
        return any(kw.lower() in text_lower for kw in keywords)
