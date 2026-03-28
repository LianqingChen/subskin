from __future__ import annotations

from collections.abc import Generator
from types import SimpleNamespace
from typing import Any, Literal
from unittest.mock import MagicMock

import pytest

from src.crawlers.pubmed_crawler import PubMedCrawler
from src.models.paper import PaperSource
from src.utils.cache import Cache


def _build_article(pmid: str, title: str = "Vitiligo study") -> SimpleNamespace:
    return SimpleNamespace(
        pmid=pmid,
        title=title,
        abstract="Abstract text",
        authors=["Alice Zhang", "Bob Li"],
        journal="Journal of Dermatology",
        year="2025",
        mesh_terms=["Vitiligo", "Skin Diseases"],
        keywords=["vitiligo", "autoimmunity"],
        doi="10.1000/example.doi",
    )


@pytest.fixture
def cache() -> Generator[Cache, None, None]:
    cache_instance = Cache()
    yield cache_instance
    cache_instance.close()


def test_search_uses_default_mesh_query_and_returns_papers(cache: Cache) -> None:
    fetcher = MagicMock()
    fetcher.pmids_for_query.return_value = ["1001"]
    fetcher.article_by_pmid.return_value = _build_article("1001")

    crawler = PubMedCrawler(
        fetcher=fetcher,
        cache=cache,
        page_size=250,
        requests_per_second=100_000,
    )
    papers = crawler.search_papers()

    assert len(papers) == 1
    paper = papers[0]
    assert paper.pmid == "1001"
    assert paper.title == "Vitiligo study"
    assert paper.abstract == "Abstract text"
    assert paper.authors == ["Alice Zhang", "Bob Li"]
    assert paper.journal == "Journal of Dermatology"
    assert paper.pub_date == "2025"
    assert paper.mesh_terms == ["Vitiligo", "Skin Diseases"]
    assert paper.keywords == ["vitiligo", "autoimmunity"]
    assert paper.source == PaperSource.PUBMED
    assert paper.crawled_at is not None

    _, kwargs = fetcher.pmids_for_query.call_args
    assert kwargs["retmax"] == 250
    assert kwargs["retstart"] == 0
    assert fetcher.pmids_for_query.call_args.args[0] == "vitiligo[MeSH Terms]"


def test_pagination_collects_more_than_1000_records(cache: Cache) -> None:
    fetcher = MagicMock()
    page_1 = [str(i) for i in range(1, 401)]
    page_2 = [str(i) for i in range(401, 801)]
    page_3 = [str(i) for i in range(801, 1101)]
    fetcher.pmids_for_query.side_effect = [page_1, page_2, page_3]
    fetcher.article_by_pmid.side_effect = lambda pmid: _build_article(pmid)

    crawler = PubMedCrawler(
        fetcher=fetcher,
        cache=cache,
        page_size=400,
        requests_per_second=100_000,
    )
    papers = crawler.search_papers()

    assert len(papers) == 1100
    assert fetcher.pmids_for_query.call_count == 3

    first_call = fetcher.pmids_for_query.call_args_list[0]
    second_call = fetcher.pmids_for_query.call_args_list[1]
    third_call = fetcher.pmids_for_query.call_args_list[2]

    assert first_call.kwargs["retstart"] == 0
    assert second_call.kwargs["retstart"] == 400
    assert third_call.kwargs["retstart"] == 800


def test_cache_prevents_redundant_api_calls(cache: Cache) -> None:
    fetcher = MagicMock()
    fetcher.pmids_for_query.return_value = ["2001"]
    fetcher.article_by_pmid.return_value = _build_article("2001")

    crawler = PubMedCrawler(
        fetcher=fetcher,
        cache=cache,
        page_size=250,
        requests_per_second=100_000,
    )

    first_run = crawler.search_papers()
    second_run = crawler.search_papers()

    assert len(first_run) == 1
    assert len(second_run) == 1
    assert fetcher.pmids_for_query.call_count == 1
    assert fetcher.article_by_pmid.call_count == 1


def test_transient_errors_are_retried_with_backoff(
    monkeypatch: pytest.MonkeyPatch, cache: Cache
) -> None:
    fetcher = MagicMock()
    fetcher.pmids_for_query.side_effect = [
        TimeoutError("timeout"),
        ["3001"],
    ]
    fetcher.article_by_pmid.return_value = _build_article("3001")

    sleep_calls: list[float] = []
    monkeypatch.setattr(
        "src.crawlers.pubmed_crawler.time.sleep",
        lambda seconds: sleep_calls.append(seconds),
    )

    crawler = PubMedCrawler(
        fetcher=fetcher,
        cache=cache,
        page_size=250,
        requests_per_second=100_000,
        max_retries=3,
        backoff_base_seconds=0.5,
    )

    papers = crawler.search_papers()

    assert len(papers) == 1
    assert fetcher.pmids_for_query.call_count == 2
    assert sleep_calls == [0.5]


def test_non_transient_error_is_not_retried(cache: Cache) -> None:
    fetcher = MagicMock()
    fetcher.pmids_for_query.side_effect = ValueError("invalid query")

    crawler = PubMedCrawler(
        fetcher=fetcher,
        cache=cache,
        page_size=250,
        requests_per_second=100_000,
        max_retries=3,
    )

    with pytest.raises(ValueError, match="invalid query"):
        crawler.search_papers()

    assert fetcher.pmids_for_query.call_count == 1


def test_rate_limiter_context_manager_is_used(
    monkeypatch: pytest.MonkeyPatch, cache: Cache
) -> None:
    class RecordingLimiter:
        def __init__(self, requests_per_second: float) -> None:
            self.requests_per_second = requests_per_second

        def __enter__(self) -> RecordingLimiter:
            counters["entered"] += 1
            return self

        def __exit__(
            self, exc_type: Any, exc_value: Any, traceback: Any
        ) -> Literal[False]:
            return False

    counters = {"entered": 0}
    monkeypatch.setattr("src.crawlers.pubmed_crawler.RateLimiter", RecordingLimiter)

    fetcher = MagicMock()
    fetcher.pmids_for_query.return_value = ["4001"]
    fetcher.article_by_pmid.return_value = _build_article("4001")

    crawler = PubMedCrawler(fetcher=fetcher, cache=cache)
    papers = crawler.search_papers()

    assert len(papers) == 1
    assert counters["entered"] == 2
