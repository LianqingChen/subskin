"""Tests for the Semantic Scholar crawler."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.crawlers.semantic_scholar_crawler import SemanticScholarCrawler
from src.models.paper import Paper, PaperSource
from src.utils.cache import Cache
from src.utils.rate_limiter import RateLimiter


def _api_paper(
    paper_id: str = "abc123",
    title: str = "Vitiligo Treatment Study",
    abstract: str | None = "A study on vitiligo treatment.",
    doi: str | None = "10.1234/test.2025",
    year: int = 2025,
    pub_date: str | None = "2025-06-15",
    venue: str = "Journal of Dermatology",
    citation_count: int = 42,
) -> dict[str, Any]:
    return {
        "paperId": paper_id,
        "title": title,
        "abstract": abstract,
        "authors": [{"name": "Alice Zhang"}, {"name": "Bob Li"}],
        "venue": venue,
        "year": year,
        "citationCount": citation_count,
        "url": f"https://www.semanticscholar.org/paper/{paper_id}",
        "externalIds": {"DOI": doi} if doi else {},
        "publicationDate": pub_date,
    }


def _api_response(
    data: list[dict[str, Any]] | None = None,
    total: int | None = None,
    offset: int = 0,
) -> dict[str, Any]:
    if data is None:
        data = [_api_paper()]
    if total is None:
        total = len(data)
    return {"total": total, "offset": offset, "data": data}


def _ok_response(json_data: dict[str, Any]) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


def _error_response(status_code: int) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    error = requests.HTTPError(f"HTTP {status_code}", response=resp)
    resp.raise_for_status.side_effect = error
    return resp


@pytest.fixture()
def cache() -> Cache:
    return Cache()


@pytest.fixture()
def rate_limiter() -> RateLimiter:
    return RateLimiter(1000)


@pytest.fixture()
def crawler(cache: Cache, rate_limiter: RateLimiter) -> SemanticScholarCrawler:
    return SemanticScholarCrawler(
        rate_limiter=rate_limiter,
        cache=cache,
        cache_ttl=3600,
        max_retries=3,
        timeout=10,
    )


class TestSearch:
    def test_returns_paper_objects(
        self, crawler: SemanticScholarCrawler
    ) -> None:
        with patch.object(
            crawler._session,
            "get",
            return_value=_ok_response(_api_response()),
        ):
            papers = crawler.search("vitiligo", max_results=10)

        assert len(papers) == 1
        paper = papers[0]
        assert isinstance(paper, Paper)
        assert paper.title == "Vitiligo Treatment Study"
        assert paper.doi == "10.1234/test.2025"
        assert paper.authors == ["Alice Zhang", "Bob Li"]
        assert paper.journal == "Journal of Dermatology"
        assert paper.pub_date == "2025-06-15"
        assert paper.citation_count == 42
        assert paper.source == PaperSource.SEMANTIC_SCHOLAR
        assert "abc123" in (paper.url or "")

    def test_empty_query_raises_value_error(
        self, crawler: SemanticScholarCrawler
    ) -> None:
        with pytest.raises(ValueError, match="empty"):
            crawler.search("")

    def test_whitespace_query_raises_value_error(
        self, crawler: SemanticScholarCrawler
    ) -> None:
        with pytest.raises(ValueError, match="empty"):
            crawler.search("   ")

    def test_no_results_returns_empty_list(
        self, crawler: SemanticScholarCrawler
    ) -> None:
        with patch.object(
            crawler._session,
            "get",
            return_value=_ok_response(_api_response(data=[], total=0)),
        ):
            papers = crawler.search("nonexistent query")

        assert papers == []


class TestPagination:
    def test_fetches_multiple_pages(
        self, crawler: SemanticScholarCrawler
    ) -> None:
        page1 = [
            _api_paper(paper_id=f"p{i}", title=f"Paper {i}")
            for i in range(3)
        ]
        page2 = [
            _api_paper(paper_id=f"p{i}", title=f"Paper {i}")
            for i in range(3, 5)
        ]

        with patch.object(
            crawler._session,
            "get",
            side_effect=[
                _ok_response(_api_response(data=page1, total=5, offset=0)),
                _ok_response(_api_response(data=page2, total=5, offset=3)),
            ],
        ) as mock_get:
            papers = crawler.search("vitiligo", max_results=10)

        assert len(papers) == 5
        assert mock_get.call_count == 2

    def test_stops_at_max_results(
        self, crawler: SemanticScholarCrawler
    ) -> None:
        page_data = [
            _api_paper(paper_id=f"p{i}", title=f"Paper {i}")
            for i in range(5)
        ]

        with patch.object(
            crawler._session,
            "get",
            return_value=_ok_response(
                _api_response(data=page_data, total=100)
            ),
        ) as mock_get:
            papers = crawler.search("vitiligo", max_results=5)

        assert len(papers) == 5
        assert mock_get.call_count == 1

    def test_custom_offset(
        self, crawler: SemanticScholarCrawler
    ) -> None:
        with patch.object(
            crawler._session,
            "get",
            return_value=_ok_response(_api_response()),
        ) as mock_get:
            crawler.search("vitiligo", max_results=10, offset=50)

        call_params = mock_get.call_args[1]["params"]
        assert call_params["offset"] == 50


class TestCaching:
    def test_cache_prevents_duplicate_requests(
        self, crawler: SemanticScholarCrawler
    ) -> None:
        with patch.object(
            crawler._session,
            "get",
            return_value=_ok_response(_api_response()),
        ) as mock_get:
            first = crawler.search("vitiligo", max_results=10)
            second = crawler.search("vitiligo", max_results=10)

        assert mock_get.call_count == 1
        assert len(first) == len(second)


class TestRateLimiting:
    def test_rate_limiter_is_invoked(self, cache: Cache) -> None:
        mock_limiter = MagicMock(spec=RateLimiter)
        mock_limiter.__enter__ = MagicMock(return_value=mock_limiter)
        mock_limiter.__exit__ = MagicMock(return_value=False)

        crawler = SemanticScholarCrawler(
            rate_limiter=mock_limiter,
            cache=cache,
            max_retries=1,
        )
        with patch.object(
            crawler._session,
            "get",
            return_value=_ok_response(_api_response()),
        ):
            crawler.search("vitiligo", max_results=10)

        mock_limiter.__enter__.assert_called()


class TestErrorHandling:
    def test_retries_on_server_error(
        self,
        crawler: SemanticScholarCrawler,
    ) -> None:
        with (
            patch.object(crawler, "_backoff_sleep") as mock_backoff,
            patch.object(
                crawler._session,
                "get",
                side_effect=[
                    _error_response(503),
                    _ok_response(_api_response()),
                ],
            ) as mock_get,
        ):
            papers = crawler.search("vitiligo", max_results=10)

        assert len(papers) == 1
        assert mock_get.call_count == 2
        mock_backoff.assert_called_once()

    def test_retries_on_timeout(
        self,
        crawler: SemanticScholarCrawler,
    ) -> None:
        with (
            patch.object(crawler, "_backoff_sleep"),
            patch.object(
                crawler._session,
                "get",
                side_effect=[
                    requests.Timeout("timed out"),
                    _ok_response(_api_response()),
                ],
            ) as mock_get,
        ):
            papers = crawler.search("vitiligo", max_results=10)

        assert len(papers) == 1
        assert mock_get.call_count == 2

    def test_retries_on_connection_error(
        self,
        crawler: SemanticScholarCrawler,
    ) -> None:
        with (
            patch.object(crawler, "_backoff_sleep"),
            patch.object(
                crawler._session,
                "get",
                side_effect=[
                    requests.ConnectionError("reset"),
                    _ok_response(_api_response()),
                ],
            ) as mock_get,
        ):
            papers = crawler.search("vitiligo", max_results=10)

        assert len(papers) == 1
        assert mock_get.call_count == 2

    def test_client_error_raises_immediately(
        self, crawler: SemanticScholarCrawler
    ) -> None:
        with patch.object(
            crawler._session,
            "get",
            return_value=_error_response(404),
        ):
            with pytest.raises(requests.HTTPError):
                crawler.search("vitiligo", max_results=10)

    def test_exhausted_retries_raises(
        self,
        crawler: SemanticScholarCrawler,
    ) -> None:
        with (
            patch.object(crawler, "_backoff_sleep"),
            patch.object(
                crawler._session,
                "get",
                side_effect=requests.Timeout("timed out"),
            ),
        ):
            with pytest.raises(requests.Timeout):
                crawler.search("vitiligo", max_results=10)

    def test_exponential_backoff(
        self,
        crawler: SemanticScholarCrawler,
    ) -> None:
        with (
            patch.object(crawler, "_backoff_sleep") as mock_backoff,
            patch.object(
                crawler._session,
                "get",
                side_effect=requests.Timeout("timed out"),
            ),
        ):
            with pytest.raises(requests.Timeout):
                crawler.search("vitiligo", max_results=10)

        assert mock_backoff.call_count == 2
        delays = [call.args[0] for call in mock_backoff.call_args_list]
        assert delays == [1.0, 2.0]


class TestParsePaper:
    def test_missing_doi(self, crawler: SemanticScholarCrawler) -> None:
        raw = _api_paper(doi=None)
        raw["externalIds"] = {}
        paper = crawler._parse_paper(raw)
        assert paper.doi is None

    def test_fallback_to_year_when_no_pub_date(
        self, crawler: SemanticScholarCrawler
    ) -> None:
        raw = _api_paper(pub_date=None)
        paper = crawler._parse_paper(raw)
        assert paper.pub_date == "2025"

    def test_no_date_info(self, crawler: SemanticScholarCrawler) -> None:
        raw = _api_paper(pub_date=None)
        raw["year"] = None
        paper = crawler._parse_paper(raw)
        assert paper.pub_date is None

    def test_url_fallback_to_paper_id(
        self, crawler: SemanticScholarCrawler
    ) -> None:
        raw = _api_paper()
        raw["url"] = None
        paper = crawler._parse_paper(raw)
        assert paper.url is not None
        assert "abc123" in paper.url

    def test_missing_authors(
        self, crawler: SemanticScholarCrawler
    ) -> None:
        raw = _api_paper()
        raw["authors"] = None
        paper = crawler._parse_paper(raw)
        assert paper.authors == []

    def test_empty_venue_becomes_none(
        self, crawler: SemanticScholarCrawler
    ) -> None:
        raw = _api_paper(venue="")
        paper = crawler._parse_paper(raw)
        assert paper.journal is None

    def test_malformed_paper_skipped_during_search(
        self, crawler: SemanticScholarCrawler
    ) -> None:
        bad_record = _api_paper(paper_id="bad")
        bad_record["externalIds"] = "not-a-dict"
        good_record = _api_paper()

        data = _api_response(data=[bad_record, good_record], total=2)
        with patch.object(
            crawler._session,
            "get",
            return_value=_ok_response(data),
        ):
            papers = crawler.search("vitiligo", max_results=10)

        assert len(papers) == 1
        assert papers[0].title == "Vitiligo Treatment Study"


class TestContextManager:
    def test_closes_session_on_exit(self) -> None:
        crawler = SemanticScholarCrawler()
        with patch.object(crawler._session, "close") as mock_close:
            with crawler:
                pass
        mock_close.assert_called_once()
