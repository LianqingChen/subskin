"""Tests for the Chinese Medical Association (CMA) crawler."""

from __future__ import annotations

import time
from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.crawlers.cma_crawler import CMACrawler
from src.models.paper import Paper, PaperSource


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def crawler() -> CMACrawler:
    """Create a CMACrawler instance with default settings."""
    return CMACrawler()


@pytest.fixture
def mock_session() -> Generator[MagicMock, None, None]:
    """Mock the requests Session."""
    with patch("src.crawlers.cma_crawler.requests.Session") as mock:
        session_instance = MagicMock()
        mock.return_value = session_instance
        yield session_instance


@pytest.fixture
def sample_search_html() -> str:
    """Sample Baidu search result HTML."""
    return """
    <html>
    <body>
        <div class="result-item">
            <a href="https://www.cma.org.cn/article/12345.html">白癜风的最新治疗方法</a>
        </div>
        <div class="result-item">
            <a href="https://www.cma.org.cn/article/67890.html">白癜风患者的日常护理</a>
        </div>
        <div class="result-item">
            <a href="https://other-site.com/article/111.html">无关链接</a>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def sample_article_html() -> str:
    """Sample CMA article HTML."""
    return """
    <html>
    <head><title>白癜风治疗新进展</title></head>
    <body>
        <div class="art-con">
            <h1>白癜风治疗新进展</h1>
            <div class="article-info">
                <span class="date">2025年3月15日</span>
            </div>
            <div class="article-content">
                <p>白癜风是一种常见的色素脱失性皮肤病，近年来治疗方法不断涌现。</p>
                <p>本文综述了近年来白癜风治疗领域的最新进展，包括JAK抑制剂、光疗、外科手术等多种治疗方法。</p>
                <p>研究表明，早期干预和个体化治疗对于改善患者预后具有重要意义。</p>
            </div>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def mock_response() -> MagicMock:
    """Create a mock response object."""
    response = MagicMock()
    response.status_code = 200
    response.text = ""
    return response


# ============================================================================
# Test CMACrawler Initialization
# ============================================================================


class TestInitialization:
    """Test CMACrawler initialization and parameter validation."""

    def test_default_initialization(self) -> None:
        """Test crawler with default parameters."""
        crawler = CMACrawler()

        assert crawler._keyword == "白癜风"
        assert crawler._base_url == "https://www.cma.org.cn"
        assert crawler._requests_per_minute == 5
        assert crawler._max_pages == 10
        assert crawler._timeout == 20
        assert crawler._max_retries == 3
        assert crawler._backoff_base_seconds == 2.0
        assert crawler._limiter is not None

    def test_custom_initialization(self) -> None:
        """Test crawler with custom parameters."""
        crawler = CMACrawler(
            keyword="JAK抑制剂",
            base_url="https://custom.cma.org.cn",
            requests_per_minute=10,
            max_pages=5,
            timeout=30,
            max_retries=5,
            backoff_base_seconds=1.5,
        )

        assert crawler._keyword == "JAK抑制剂"
        assert crawler._base_url == "https://custom.cma.org.cn"
        assert crawler._requests_per_minute == 10
        assert crawler._max_pages == 5
        assert crawler._timeout == 30
        assert crawler._max_retries == 5
        assert crawler._backoff_base_seconds == 1.5

    def test_max_pages_zero_raises_error(self) -> None:
        """Test that max_pages=0 raises ValueError."""
        with pytest.raises(ValueError, match="max_pages must be positive"):
            CMACrawler(max_pages=0)

    def test_max_pages_negative_raises_error(self) -> None:
        """Test that negative max_pages raises ValueError."""
        with pytest.raises(ValueError, match="max_pages must be positive"):
            CMACrawler(max_pages=-1)

    def test_requests_per_minute_zero_raises_error(self) -> None:
        """Test that requests_per_minute=0 raises ValueError."""
        with pytest.raises(ValueError, match="requests_per_minute must be positive"):
            CMACrawler(requests_per_minute=0)

    def test_requests_per_minute_negative_raises_error(self) -> None:
        """Test that negative requests_per_minute raises ValueError."""
        with pytest.raises(ValueError, match="requests_per_minute must be positive"):
            CMACrawler(requests_per_minute=-5)

    def test_max_retries_negative_raises_error(self) -> None:
        """Test that negative max_retries raises ValueError."""
        with pytest.raises(ValueError, match="max_retries must be non-negative"):
            CMACrawler(max_retries=-1)

    def test_backoff_base_zero_raises_error(self) -> None:
        """Test that backoff_base_seconds=0 raises ValueError."""
        with pytest.raises(ValueError, match="backoff_base_seconds must be positive"):
            CMACrawler(backoff_base_seconds=0)

    def test_backoff_base_negative_raises_error(self) -> None:
        """Test that negative backoff_base_seconds raises ValueError."""
        with pytest.raises(ValueError, match="backoff_base_seconds must be positive"):
            CMACrawler(backoff_base_seconds=-1.0)


# ============================================================================
# Test Rate Limiter Integration
# ============================================================================


class TestRateLimiterIntegration:
    """Test rate limiter integration in the crawler."""

    def test_rate_limiter_is_initialized(self) -> None:
        """Test that rate limiter is properly initialized."""
        crawler = CMACrawler(requests_per_minute=60)

        assert crawler._limiter is not None
        assert crawler._limiter._rate == 1.0  # 60/60

    def test_rate_limiter_acquire_is_called_during_request(
        self, crawler: CMACrawler, mock_response: MagicMock
    ) -> None:
        """Test that rate limiter acquire is called during request."""
        mock_response.text = "<html></html>"

        with patch.object(crawler._limiter, "acquire") as mock_acquire:
            with patch.object(crawler._session, "get", return_value=mock_response):
                crawler._make_request("https://example.com")

        mock_acquire.assert_called_once()


# ============================================================================
# Test Request Retry Logic (_make_request)
# ============================================================================


class TestMakeRequest:
    """Test the _make_request method with retry logic."""

    def test_successful_request_returns_response(
        self, crawler: CMACrawler, mock_response: MagicMock
    ) -> None:
        """Test successful request returns response."""
        mock_response.text = "<html>success</html>"

        with patch.object(crawler._session, "get", return_value=mock_response):
            result = crawler._make_request("https://example.com")

        assert result is not None
        assert result.text == "<html>success</html>"

    def test_429_status_triggers_retry_with_backoff(self, crawler: CMACrawler) -> None:
        """Test 429 status triggers retry with exponential backoff."""
        error_response = MagicMock()
        error_response.status_code = 429

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.text = "<html>success</html>"

        with patch.object(
            crawler._session, "get", side_effect=[error_response, success_response]
        ):
            with patch("time.sleep") as mock_sleep:
                result = crawler._make_request("https://example.com")

        assert result is not None
        assert result.text == "<html>success</html>"
        mock_sleep.assert_called_once()

    def test_request_exception_triggers_retry(self, crawler: CMACrawler) -> None:
        """Test request exception triggers retry."""
        success_response = MagicMock()
        success_response.status_code = 200
        success_response.text = "<html>success</html>"

        with patch.object(
            crawler._session,
            "get",
            side_effect=[requests.Timeout("timeout"), success_response],
        ):
            with patch("time.sleep"):
                result = crawler._make_request("https://example.com")

        assert result is not None
        assert result.text == "<html>success</html>"

    def test_all_retries_exhausted_returns_none(self, crawler: CMACrawler) -> None:
        """Test that all retries exhausted returns None."""
        error_response = MagicMock()
        error_response.status_code = 500

        with patch.object(crawler._session, "get", return_value=error_response):
            with patch("time.sleep"):
                result = crawler._make_request("https://example.com")

        assert result is None

    def test_post_request_method(
        self, crawler: CMACrawler, mock_response: MagicMock
    ) -> None:
        """Test POST request method."""
        mock_response.text = "<html>post success</html>"

        with patch.object(crawler._session, "post", return_value=mock_response):
            result = crawler._make_request(
                "https://example.com", method="POST", data={"key": "value"}
            )

        assert result is not None
        assert result.text == "<html>post success</html>"


# ============================================================================
# Test Article Parsing (_parse_article)
# ============================================================================


class TestParseArticle:
    """Test the _parse_article method."""

    def test_parse_article_with_absolute_url(
        self, crawler: CMACrawler, sample_article_html: str
    ) -> None:
        """Test parsing article with absolute URL."""
        with patch.object(
            crawler, "_make_request", return_value=MagicMock(text=sample_article_html)
        ):
            paper = crawler._parse_article(
                "https://www.cma.org.cn/article/12345.html", "白癜风治疗新进展"
            )

        assert paper is not None
        assert paper.title == "白癜风治疗新进展"
        assert paper.journal == "中华医学会"
        assert paper.source == PaperSource.OTHER
        assert "白癜风" in paper.keywords
        assert paper.url == "https://www.cma.org.cn/article/12345.html"

    def test_parse_article_with_relative_url(
        self, crawler: CMACrawler, sample_article_html: str
    ) -> None:
        """Test parsing article with relative URL."""
        with patch.object(
            crawler, "_make_request", return_value=MagicMock(text=sample_article_html)
        ):
            paper = crawler._parse_article("/article/12345.html", "白癜风治疗新进展")

        assert paper is not None
        assert "cma.org.cn/article/12345.html" in paper.url

    def test_parse_article_no_content_returns_none(self, crawler: CMACrawler) -> None:
        """Test that parsing article with no content returns None."""
        empty_html = "<html><body></body></html>"

        with patch.object(
            crawler, "_make_request", return_value=MagicMock(text=empty_html)
        ):
            paper = crawler._parse_article(
                "https://www.cma.org.cn/article/12345.html", "Empty Article"
            )

        assert paper is None

    def test_parse_article_extracts_publication_date(self, crawler: CMACrawler) -> None:
        """Test that publication date is extracted correctly."""
        html = """
        <html>
        <body>
            <div class="art-con">
                <span class="date">2025年3月15日</span>
                <div class="article-content">
                    <p>白癜风是一种常见的色素脱失性皮肤病。</p>
                </div>
            </div>
        </body>
        </html>
        """

        with patch.object(crawler, "_make_request", return_value=MagicMock(text=html)):
            paper = crawler._parse_article(
                "https://www.cma.org.cn/article/12345.html", "白癜风治疗新进展"
            )

        assert paper is not None
        assert paper.pub_date == "2025-03-15"

    def test_parse_article_truncates_long_abstract(self, crawler: CMACrawler) -> None:
        """Test that long abstracts are truncated."""
        long_text = "这是一段很长的文本。" * 500  # Very long text
        html = f"""
        <html>
        <body>
            <div class="art-con">
                <div class="article-content">
                    <p>{long_text}</p>
                </div>
            </div>
        </body>
        </html>
        """

        with patch.object(crawler, "_make_request", return_value=MagicMock(text=html)):
            paper = crawler._parse_article(
                "https://www.cma.org.cn/article/12345.html", "Test Article"
            )

        assert paper is not None
        assert len(paper.abstract) <= 2000
        assert paper.abstract.endswith("...")

    def test_parse_article_failed_request_returns_none(
        self, crawler: CMACrawler
    ) -> None:
        """Test that failed request returns None."""
        with patch.object(crawler, "_make_request", return_value=None):
            paper = crawler._parse_article(
                "https://www.cma.org.cn/article/12345.html", "Test Article"
            )

        assert paper is None


# ============================================================================
# Test Search Result Extraction (_extract_search_results)
# ============================================================================


class TestExtractSearchResults:
    """Test the _extract_search_results method."""

    def test_extract_results_from_baidu_html(
        self, crawler: CMACrawler, sample_search_html: str
    ) -> None:
        """Test extracting search results from Baidu HTML."""
        results = crawler._extract_search_results(sample_search_html)

        assert len(results) == 2
        assert results[0]["title"] == "白癜风的最新治疗方法"
        assert "cma.org.cn" in results[0]["url"]
        assert results[1]["title"] == "白癜风患者的日常护理"

    def test_empty_html_returns_empty_list(self, crawler: CMACrawler) -> None:
        """Test that empty HTML returns empty list."""
        results = crawler._extract_search_results("")
        assert results == []

    def test_no_results_returns_empty_list(self, crawler: CMACrawler) -> None:
        """Test that HTML with no results returns empty list."""
        html = '<html><body><div class="content">No results found</div></body></html>'
        results = crawler._extract_search_results(html)
        assert results == []

    def test_filters_non_cma_links(self, crawler: CMACrawler) -> None:
        """Test that non-CMA links are filtered out."""
        html = """
        <html>
        <body>
            <div class="result-item">
                <a href="https://www.cma.org.cn/article/12345.html">CMA Article</a>
            </div>
            <div class="result-item">
                <a href="https://www.other-site.com/article/67890.html">Other Site</a>
            </div>
        </body>
        </html>
        """
        results = crawler._extract_search_results(html)

        assert len(results) == 1
        assert "cma.org.cn" in results[0]["url"]

    def test_skips_navigation_links(self, crawler: CMACrawler) -> None:
        """Test that navigation links are skipped."""
        html = """
        <html>
        <body>
            <div class="result-item">
                <a href="https://www.cma.org.cn/article/12345.html">Valid Article</a>
            </div>
            <div class="result-item">
                <a href="https://www.cma.org.cn/col/index.html">Navigation Page</a>
            </div>
            <div class="result-item">
                <a href="https://www.cma.org.cn/login.html">Login Page</a>
            </div>
        </body>
        </html>
        """
        results = crawler._extract_search_results(html)

        assert len(results) == 1
        assert "article/12345" in results[0]["url"]

    def test_filters_by_keyword_in_title(self, crawler: CMACrawler) -> None:
        """Test that results without keyword in title are filtered."""
        html = """
        <html>
        <body>
            <div class="result-item">
                <a href="https://www.cma.org.cn/article/12345.html">白癜风的最新治疗方法</a>
            </div>
            <div class="result-item">
                <a href="https://www.cma.org.cn/article/67890.html">其他疾病的治疗</a>
            </div>
        </body>
        </html>
        """
        results = crawler._extract_search_results(html)

        assert len(results) == 1
        assert "白癜风" in results[0]["title"]

    def test_handles_string_items_gracefully(self, crawler: CMACrawler) -> None:
        """Test that string items in results are handled gracefully."""
        html = """
        <html>
        <body>
            <div class="result-item">
                <a href="https://www.cma.org.cn/article/12345.html">白癜风治疗</a>
            </div>
        </body>
        </html>
        """
        results = crawler._extract_search_results(html)
        assert len(results) == 1


# ============================================================================
# Test Main Crawl Method
# ============================================================================


class TestCrawl:
    """Test the main crawl method."""

    def test_crawl_with_no_results(self, crawler: CMACrawler) -> None:
        """Test crawl when no results are found."""
        with patch.object(
            crawler, "_make_request", return_value=MagicMock(text="<html></html>")
        ):
            papers = crawler.crawl()

        assert papers == []

    def test_crawl_stops_at_max_pages(self, crawler: CMACrawler) -> None:
        """Test that crawl stops at max_pages."""
        search_html = """
        <html>
        <body>
            <div class="result-item">
                <a href="https://www.cma.org.cn/article/12345.html">白癜风治疗</a>
            </div>
        </body>
        </html>
        """

        article_html = """
        <html>
        <body>
            <div class="art-con">
                <div class="article-content">
                    <p>白癜风治疗方法。</p>
                </div>
            </div>
        </body>
        </html>
        """

        def mock_make_request(url: str, **kwargs: Any) -> MagicMock:
            response = MagicMock()
            if "zhannei.baidu.com" in url:
                response.text = search_html
            else:
                response.text = article_html
            return response

        crawler = CMACrawler(max_pages=2)

        with patch.object(crawler, "_make_request", side_effect=mock_make_request):
            papers = crawler.crawl()

        # Should stop after max_pages
        assert len(papers) <= 2

    def test_search_vitiligo_calls_crawl(self, crawler: CMACrawler) -> None:
        """Test that search_vitiligo calls crawl method."""
        with patch.object(crawler, "crawl", return_value=[]) as mock_crawl:
            crawler.search_vitiligo()

        mock_crawl.assert_called_once()

    def test_crawl_logs_progress(self, crawler: CMACrawler) -> None:
        """Test that crawl logs progress."""
        with patch.object(crawler, "_make_request", return_value=None):
            with patch("src.crawlers.cma_crawler.logger") as mock_logger:
                crawler.crawl()

        mock_logger.info.assert_any_call(
            f"Starting CMA (中华医学会) crawl for keyword: {crawler._keyword}"
        )


# ============================================================================
# Test Error Handling and Edge Cases
# ============================================================================


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_make_request_handles_connection_error(self, crawler: CMACrawler) -> None:
        """Test handling of connection errors."""
        with patch.object(
            crawler._session,
            "get",
            side_effect=requests.ConnectionError("Connection failed"),
        ):
            with patch("time.sleep"):
                result = crawler._make_request("https://example.com")

        assert result is None

    def test_make_request_handles_timeout(self, crawler: CMACrawler) -> None:
        """Test handling of timeout errors."""
        with patch.object(
            crawler._session, "get", side_effect=requests.Timeout("Request timed out")
        ):
            with patch("time.sleep"):
                result = crawler._make_request("https://example.com")

        assert result is None

    def test_parse_article_handles_malformed_html(self, crawler: CMACrawler) -> None:
        """Test parsing article with malformed HTML."""
        malformed_html = "<html><body><div>Not proper HTML"

        with patch.object(
            crawler, "_make_request", return_value=MagicMock(text=malformed_html)
        ):
            paper = crawler._parse_article(
                "https://www.cma.org.cn/article/12345.html", "Test Article"
            )

        assert paper is not None
        assert paper.title == "Test Article"

    def test_crawl_handles_no_results_gracefully(self, crawler: CMACrawler) -> None:
        """Test that crawl handles no results gracefully."""
        with patch.object(
            crawler, "_make_request", return_value=MagicMock(text="<html></html>")
        ):
            papers = crawler.crawl()

        assert papers == []

    def test_crawl_handles_request_failure(self, crawler: CMACrawler) -> None:
        """Test that crawl handles request failure."""
        with patch.object(crawler, "_make_request", return_value=None):
            papers = crawler.crawl()

        assert papers == []

    def test_session_headers_are_set_correctly(self, crawler: CMACrawler) -> None:
        """Test that session headers are set correctly."""
        headers = crawler._session.headers

        assert "User-Agent" in headers
        assert "Mozilla/5.0" in headers["User-Agent"]
        assert "Accept" in headers
        assert "Accept-Language" in headers
        assert "zh-CN" in headers["Accept-Language"]


# ============================================================================
# Test Edge Cases and Boundary Conditions
# ============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_keyword_allowed(self) -> None:
        """Test that empty keyword is allowed (uses default)."""
        crawler = CMACrawler(keyword="")
        assert crawler._keyword == ""

    def test_very_long_keyword(self) -> None:
        """Test that very long keyword is handled."""
        long_keyword = "白癜风" * 100
        crawler = CMACrawler(keyword=long_keyword)
        assert crawler._keyword == long_keyword

    def test_max_retries_zero(self) -> None:
        """Test that max_retries=0 is allowed."""
        crawler = CMACrawler(max_retries=0)
        assert crawler._max_retries == 0

    def test_very_small_timeout(self) -> None:
        """Test that very small timeout is handled."""
        crawler = CMACrawler(timeout=1)
        assert crawler._timeout == 1

    def test_very_large_max_pages(self) -> None:
        """Test that very large max_pages is handled."""
        crawler = CMACrawler(max_pages=1000)
        assert crawler._max_pages == 1000

    def test_single_result_extraction(self, crawler: CMACrawler) -> None:
        """Test extraction of single result."""
        html = """
        <html>
        <body>
            <div class="result-item">
                <a href="https://www.cma.org.cn/article/12345.html">白癜风治疗</a>
            </div>
        </body>
        </html>
        """

        results = crawler._extract_search_results(html)

        assert len(results) == 1
        assert results[0]["title"] == "白癜风治疗"


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests for the crawler."""

    def test_full_crawl_flow(
        self, sample_search_html: str, sample_article_html: str
    ) -> None:
        """Test the full crawl flow with mocked responses."""
        crawler = CMACrawler(max_pages=1)

        def mock_make_request(url: str, **kwargs: Any) -> MagicMock:
            response = MagicMock()
            if "zhannei.baidu.com" in url:
                response.text = sample_search_html
            else:
                response.text = sample_article_html
            return response

        with patch.object(crawler, "_make_request", side_effect=mock_make_request):
            papers = crawler.crawl()

        assert len(papers) == 2
        for paper in papers:
            assert isinstance(paper, Paper)
            assert paper.source == PaperSource.OTHER
            assert paper.journal == "中华医学会"

    def test_multiple_pages_crawl(self) -> None:
        """Test crawling multiple pages."""
        crawler = CMACrawler(max_pages=2)

        search_html_page1 = """
        <html>
        <body>
            <div class="result-item">
                <a href="https://www.cma.org.cn/article/1.html">白癜风文章1</a>
            </div>
            <div class="result-item">
                <a href="https://www.cma.org.cn/article/2.html">白癜风文章2</a>
            </div>
            <div class="result-item">
                <a href="https://www.cma.org.cn/article/3.html">白癜风文章3</a>
            </div>
        </body>
        </html>
        """

        search_html_page2 = """
        <html>
        <body>
            <div class="result-item">
                <a href="https://www.cma.org.cn/article/4.html">白癜风文章4</a>
            </div>
        </body>
        </html>
        """

        article_html = """
        <html>
        <body>
            <div class="art-con">
                <div class="article-content">
                    <p>文章内容。</p>
                </div>
            </div>
        </body>
        </html>
        """

        call_count = 0

        def mock_make_request(url: str, **kwargs: Any) -> MagicMock:
            nonlocal call_count
            response = MagicMock()
            if "zhannei.baidu.com" in url:
                call_count += 1
                if call_count == 1:
                    response.text = search_html_page1
                else:
                    response.text = search_html_page2
            else:
                response.text = article_html
            return response

        with patch.object(crawler, "_make_request", side_effect=mock_make_request):
            papers = crawler.crawl()

        # Should have papers from both pages (but limited by max_pages=2 and result count)
        assert len(papers) >= 1


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
