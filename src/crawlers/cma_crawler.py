"""Chinese Medical Association (中华医学会) crawler for the SubSkin project.

This module provides a crawler for fetching vitiligo-related articles from
the 中华医学会 official website科普频道 and other publicly accessible articles.
"""

from __future__ import annotations

import logging
import time
import re
import requests
from datetime import datetime, timezone
from typing import Any, List, Optional

from bs4 import BeautifulSoup
from src.models.paper import Paper, PaperSource
from src.utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class CMACrawler:
    """Crawler for Chinese Medical Association (中华医学会) articles related to vitiligo.

    This crawler searches for vitiligo-related articles on the main中华医学会官网
   科普与健康频道 (https://www.cma.org.cn/col/col12/index.html), which contains
    publicly accessible articles for the public.

    Args:
        keyword: Search keyword, defaults to "白癜风".
        base_url: Base URL for中华医学会 website.
        requests_per_minute: Rate limit for polite crawling.
        max_pages: Maximum number of search result pages to crawl.
        timeout: Request timeout in seconds.
        max_retries: Number of retry attempts for network failures.
        backoff_base_seconds: Base delay for exponential backoff.
    """

    DEFAULT_KEYWORD = "白癜风"
    BASE_URL = "https://www.cma.org.cn"
    SEARCH_URL = "https://zhannei.baidu.com/cse/site"
    DEFAULT_REQUESTS_PER_MINUTE = 5
    DEFAULT_MAX_PAGES = 10
    DEFAULT_TIMEOUT = 20
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_BACKOFF_BASE = 2.0

    def __init__(
        self,
        *,
        keyword: str = DEFAULT_KEYWORD,
        base_url: str = BASE_URL,
        requests_per_minute: float = DEFAULT_REQUESTS_PER_MINUTE,
        max_pages: int = DEFAULT_MAX_PAGES,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_base_seconds: float = DEFAULT_BACKOFF_BASE,
    ) -> None:
        if max_pages <= 0:
            raise ValueError("max_pages must be positive")
        if requests_per_minute <= 0:
            raise ValueError("requests_per_minute must be positive")
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if backoff_base_seconds <= 0:
            raise ValueError("backoff_base_seconds must be positive")

        self._keyword = keyword
        self._base_url = base_url
        self._requests_per_minute = requests_per_minute
        self._max_pages = max_pages
        self._timeout = timeout
        self._max_retries = max_retries
        self._backoff_base_seconds = backoff_base_seconds
        self._limiter = RateLimiter(requests_per_second=requests_per_minute / 60.0)

        # Session with persistent cookies
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
                      "image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Referer": "https://www.cma.org.cn/",
        })

    def _make_request(
        self,
        url: str,
        method: str = "GET",
        params: Optional[dict[str, Any]] = None,
        data: Optional[dict[str, Any]] = None,
    ) -> Optional[requests.Response]:
        """Make a rate-limited request with retries and exponential backoff."""
        for attempt in range(self._max_retries + 1):
            self._limiter.acquire()

            try:
                if method.upper() == "GET":
                    response = self._session.get(
                        url,
                        params=params,
                        timeout=self._timeout,
                    )
                else:
                    response = self._session.post(
                        url,
                        data=data,
                        params=params,
                        timeout=self._timeout,
                    )

                if response.status_code == 200:
                    return response
                elif response.status_code == 429:
                    wait_time = self._backoff_base_seconds ** (attempt + 1)
                    logger.warning(f"Rate limited (429), waiting {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.warning(
                        f"Request failed: {url} - status {response.status_code}"
                    )

            except requests.exceptions.RequestException as e:
                wait_time = self._backoff_base_seconds ** attempt
                logger.warning(
                    f"Request exception for {url}: {str(e)}, "
                    f"waiting {wait_time}s before retry (attempt {attempt + 1}/{self._max_retries + 1})"
                )
                time.sleep(wait_time)

        logger.error(f"All {self._max_retries + 1} attempts failed for {url}")
        return None

    def _parse_article(self, article_url: str, title: str) -> Optional[Paper]:
        """Parse article page to get content and metadata."""
        # Handle relative URLs
        if not article_url.startswith("http"):
            if article_url.startswith("/"):
                article_url = self._base_url + article_url
            else:
                article_url = self._base_url + "/" + article_url

        response = self._make_request(article_url)
        if not response:
            return None

        soup = BeautifulSoup(response.text, "html.parser")

        # Find article content on CMA site
        content_selectors = [
            ".art-con",
            ".article-content",
            ".container-text",
            "#zoom-content",
            "#content",
            ".content",
        ]

        content = None
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem and len(content_elem.get_text(strip=True)) > 100:
                content = content_elem
                break

        if not content:
            body = soup.find("body")
            if body and len(body.get_text(strip=True)) > 100:
                content = body

        if not content:
            logger.warning(f"Could not find content for article: {article_url}")
            return None

        # Extract text and clean up
        text = content.get_text("\n", strip=True)
        text = re.sub(r"\n\s*\n", "\n\n", text)

        # Get abstract from first paragraph
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip() and len(p.strip()) > 20]
        abstract = paragraphs[0] if paragraphs else text
        if abstract and len(abstract) > 2000:
            abstract = abstract[:1997] + "..."

        # Try to find publication date
        pub_date = None
        date_elem = soup.find(string=re.compile(r"\d{4}年\d{1,2}月"))
        if not date_elem:
            date_elem = soup.find(class_=re.compile(r"date|time|publish", re.I))
        if date_elem:
            date_text = date_elem.get_text(strip=True) if hasattr(date_elem, 'get_text') else str(date_elem)
            date_match = re.search(r"(\d{4})[年/-](\d{1,2})[月/-](\d{1,2})?", date_text)
            if date_match:
                year = date_match.group(1)
                month = date_match.group(2).zfill(2)
                day = date_match.group(3).zfill(2) if date_match.group(3) else "01"
                pub_date = f"{year}-{month}-{day}"

        # Create Paper object
        paper = Paper(
            title=title,
            abstract=abstract,
            authors=[],
            journal="中华医学会",
            pub_date=pub_date,
            source=PaperSource.OTHER,
            url=article_url,
            mesh_terms=["白癜风"],
            keywords=["白癜风"],
        )

        return paper

    def _extract_search_results(self, html: str) -> List[dict[str, Any]]:
        """Extract article links from Baidu site search results."""
        soup = BeautifulSoup(html, "html.parser")
        results: List[dict[str, Any]] = []

        # Baidu site search result items
        result_items = soup.select(".result-item") or soup.select(".result") or soup.select("a[href*=cma.org.cn]")

        if not result_items:
            return results

        for item in result_items:
            if isinstance(item, str):
                continue

            link = item if item.has_attr("href") else item.find("a", href=True)
            if not link or not link.has_attr("href"):
                continue

            href = link["href"]
            # Only include links from cma.org.cn
            if "cma.org.cn" not in href:
                continue
            # Skip navigation links, only include article pages
            if any(skip in href for skip in ["col/index", "login", "register", "search"]):
                continue

            title = link.get_text(strip=True)
            if not title or self._keyword not in title:
                continue

            results.append({
                "title": title,
                "url": href,
            })

        return results

    def crawl(self) -> List[Paper]:
        """Crawl中华医学会 for articles matching the keyword.

        Uses Baidu site search to find all pages on cma.org.cn containing the keyword.
        This approach is more reliable than searching the site itself.

        Returns:
            List of Paper objects with article content.
        """
        all_papers: List[Paper] = []
        page = 1

        logger.info(f"Starting CMA (中华医学会) crawl for keyword: {self._keyword}")
        logger.info(f"Using Baidu site search on cma.org.cn")

        while page <= self._max_pages:
            logger.info(f"Crawling page {page}/{self._max_pages}")

            # Use Baidu site search to find relevant articles on cma.org.cn
            params = {
                "q": f"{self._keyword} site:cma.org.cn",
                "p": (page - 1),  # page number starts from 0
            }

            response = self._make_request(
                self.SEARCH_URL,
                method="GET",
                params=params
            )

            if not response:
                logger.error(f"Failed to get search page {page}, stopping")
                break

            results = self._extract_search_results(response.text)
            if not results:
                logger.info(f"No more results on page {page}, stopping")
                break

            logger.info(f"Found {len(results)} results containing keyword on page {page}")

            for result in results:
                paper = self._parse_article(
                    article_url=result["url"],
                    title=result["title"],
                )
                if paper:
                    all_papers.append(paper)
                    logger.debug(f"Parsed: {paper.title}")

            if len(results) < 3:
                break

            page += 1

        logger.info(f"Crawl completed. Total articles collected: {len(all_papers)}")
        return all_papers

    def search_vitiligo(self) -> List[Paper]:
        """Convenience method to search for vitiligo articles.

        This is the main entry point that matches the crawler interface
        expected by the scheduler.
        """
        return self.crawl()