"""Tests for the data deduplication module."""

from __future__ import annotations

from datetime import datetime
from typing import List

import pytest

from src.models.paper import Paper, PaperSource
from src.processors.deduplicator import Deduplicator, deduplicate_papers


@pytest.fixture
def deduplicator() -> Deduplicator:
    return Deduplicator()


def create_paper(
    pmid: str | None = None,
    doi: str | None = None,
    title: str = "Test Paper",
    abstract: str | None = "Test abstract",
    authors: List[str] | None = None,
    journal: str | None = "Test Journal",
    pub_date: str | None = "2024-01-01",
    mesh_terms: List[str] | None = None,
    keywords: List[str] | None = None,
    source: PaperSource = PaperSource.PUBMED,
    url: str | None = None,
    citation_count: int | None = None,
    crawled_at: str | None = None,
) -> Paper:
    """Helper to create Paper objects for testing."""
    if authors is None:
        authors = ["Author One", "Author Two"]
    if mesh_terms is None:
        mesh_terms = ["Term1", "Term2"]
    if keywords is None:
        keywords = ["keyword1", "keyword2"]
    if crawled_at is None:
        crawled_at = datetime.now().isoformat()

    return Paper(
        pmid=pmid,
        doi=doi,
        title=title,
        abstract=abstract,
        authors=authors,
        journal=journal,
        pub_date=pub_date,
        mesh_terms=mesh_terms,
        keywords=keywords,
        source=source,
        url=url,
        citation_count=citation_count,
        crawled_at=crawled_at,
        translated=False,
        summarized=False,
        language="en",
    )


class TestDeduplicationBasic:
    """Basic deduplication tests."""

    def test_empty_list_returns_empty(self, deduplicator: Deduplicator) -> None:
        result = deduplicator.deduplicate([])
        assert result == []

    def test_single_paper_returns_same(self, deduplicator: Deduplicator) -> None:
        paper = create_paper(pmid="12345", doi="10.1000/test")
        result = deduplicator.deduplicate([paper])
        assert result == [paper]

    def test_duplicate_by_doi(self, deduplicator: Deduplicator) -> None:
        """Two papers with same DOI should be deduplicated."""
        paper1 = create_paper(
            pmid="12345",
            doi="10.1000/test",
            title="Paper One",
            source=PaperSource.PUBMED,
        )
        paper2 = create_paper(
            pmid="67890",
            doi="10.1000/test",
            title="Paper Two",
            source=PaperSource.SEMANTIC_SCHOLAR,
        )
        result = deduplicator.deduplicate([paper1, paper2])
        assert len(result) == 1
        merged = result[0]
        assert merged.doi == "10.1000/test"
        assert merged.pmid == "12345"
        assert merged.title == "Paper One"

    def test_duplicate_by_pmid(self, deduplicator: Deduplicator) -> None:
        """Two papers with same PMID (no DOI) should be deduplicated."""
        paper1 = create_paper(
            pmid="12345",
            doi=None,
            title="Paper One",
            source=PaperSource.PUBMED,
        )
        paper2 = create_paper(
            pmid="12345",
            doi=None,
            title="Paper Two",
            source=PaperSource.SEMANTIC_SCHOLAR,
        )
        result = deduplicator.deduplicate([paper1, paper2])
        assert len(result) == 1
        merged = result[0]
        assert merged.pmid == "12345"
        assert merged.doi is None

    def test_no_identifiers_use_fallback(self, deduplicator: Deduplicator) -> None:
        """Papers without DOI/PMID use title+author hash."""
        paper1 = create_paper(
            pmid=None,
            doi=None,
            title="Same Title",
            authors=["Author A"],
            pub_date="2024",
        )
        paper2 = create_paper(
            pmid=None,
            doi=None,
            title="Same Title",
            authors=["Author A"],
            pub_date="2024",
        )
        result = deduplicator.deduplicate([paper1, paper2])
        assert len(result) == 1

    def test_different_papers_no_deduplication(self, deduplicator: Deduplicator) -> None:
        """Different papers should not be deduplicated."""
        paper1 = create_paper(doi="10.1000/one", title="Paper One")
        paper2 = create_paper(doi="10.1000/two", title="Paper Two")
        paper3 = create_paper(pmid="12345", title="Paper Three")
        result = deduplicator.deduplicate([paper1, paper2, paper3])
        assert len(result) == 3


class TestMergeStrategies:
    """Test specific field merging strategies."""

    def test_merge_title_prefers_longer(self, deduplicator: Deduplicator) -> None:
        paper1 = create_paper(
            doi="10.1000/test",
            title="Short",
            source=PaperSource.PUBMED,
        )
        paper2 = create_paper(
            doi="10.1000/test",
            title="Much Longer Title With More Details",
            source=PaperSource.SEMANTIC_SCHOLAR,
        )
        result = deduplicator.deduplicate([paper1, paper2])
        merged = result[0]
        assert merged.title == "Much Longer Title With More Details"

    def test_merge_abstract_prefers_longer(self, deduplicator: Deduplicator) -> None:
        paper1 = create_paper(
            doi="10.1000/test",
            abstract="Short abstract",
            source=PaperSource.PUBMED,
        )
        paper2 = create_paper(
            doi="10.1000/test",
            abstract="Much longer and more detailed abstract with additional information",
            source=PaperSource.SEMANTIC_SCHOLAR,
        )
        result = deduplicator.deduplicate([paper1, paper2])
        merged = result[0]
        assert merged.abstract == "Much longer and more detailed abstract with additional information"

    def test_merge_authors_union(self, deduplicator: Deduplicator) -> None:
        paper1 = create_paper(
            doi="10.1000/test",
            authors=["Author A", "Author B"],
            source=PaperSource.PUBMED,
        )
        paper2 = create_paper(
            doi="10.1000/test",
            authors=["Author B", "Author C"],
            source=PaperSource.SEMANTIC_SCHOLAR,
        )
        result = deduplicator.deduplicate([paper1, paper2])
        merged = result[0]
        assert set(merged.authors) == {"Author A", "Author B", "Author C"}

    def test_merge_journal_prefers_pubmed(self, deduplicator: Deduplicator) -> None:
        paper1 = create_paper(
            doi="10.1000/test",
            journal="PubMed Journal",
            source=PaperSource.PUBMED,
        )
        paper2 = create_paper(
            doi="10.1000/test",
            journal="Semantic Scholar Venue",
            source=PaperSource.SEMANTIC_SCHOLAR,
        )
        result = deduplicator.deduplicate([paper1, paper2])
        merged = result[0]
        assert merged.journal == "PubMed Journal"

    def test_merge_mesh_terms_union(self, deduplicator: Deduplicator) -> None:
        paper1 = create_paper(
            doi="10.1000/test",
            mesh_terms=["Term1", "Term2"],
            source=PaperSource.PUBMED,
        )
        paper2 = create_paper(
            doi="10.1000/test",
            mesh_terms=["Term2", "Term3"],
            source=PaperSource.SEMANTIC_SCHOLAR,
        )
        result = deduplicator.deduplicate([paper1, paper2])
        merged = result[0]
        assert set(merged.mesh_terms) == {"Term1", "Term2", "Term3"}

    def test_merge_citation_count_takes_max(self, deduplicator: Deduplicator) -> None:
        paper1 = create_paper(
            doi="10.1000/test",
            citation_count=10,
            source=PaperSource.PUBMED,
        )
        paper2 = create_paper(
            doi="10.1000/test",
            citation_count=25,
            source=PaperSource.SEMANTIC_SCHOLAR,
        )
        result = deduplicator.deduplicate([paper1, paper2])
        merged = result[0]
        assert merged.citation_count == 25

    def test_merge_missing_fields_filled(self, deduplicator: Deduplicator) -> None:
        """Test that missing fields in one paper are filled from the other."""
        paper1 = create_paper(
            pmid="12345",
            doi="10.1000/test",
            citation_count=None,
            url=None,
            source=PaperSource.PUBMED,
        )
        paper2 = create_paper(
            pmid="12345",
            doi="10.1000/test",
            citation_count=15,
            url="https://example.com",
            source=PaperSource.SEMANTIC_SCHOLAR,
        )
        result = deduplicator.deduplicate([paper1, paper2])
        merged = result[0]
        assert merged.pmid == "12345"
        assert merged.doi == "10.1000/test"
        assert merged.citation_count == 15
        assert merged.url == "https://example.com"


class TestSourcePreference:
    """Test source preference ordering."""

    def test_default_source_order(self, deduplicator: Deduplicator) -> None:
        """Default order: PubMed > Semantic Scholar."""
        paper1 = create_paper(
            doi="10.1000/test",
            title="PubMed Title",
            journal="PubMed Journal",
            source=PaperSource.SEMANTIC_SCHOLAR,
        )
        paper2 = create_paper(
            doi="10.1000/test",
            title="Semantic Scholar Title",
            journal="Semantic Scholar Venue",
            source=PaperSource.PUBMED,
        )
        result = deduplicator.deduplicate([paper1, paper2])
        merged = result[0]
        assert merged.source == PaperSource.PUBMED
        assert merged.title == "Semantic Scholar Title"

    def test_custom_source_order(self) -> None:
        """Test with custom source preference order."""
        deduplicator = Deduplicator(
            prefer_source_order=[PaperSource.SEMANTIC_SCHOLAR, PaperSource.PUBMED]
        )
        paper1 = create_paper(
            doi="10.1000/test",
            title="PubMed Title",
            source=PaperSource.PUBMED,
        )
        paper2 = create_paper(
            doi="10.1000/test",
            title="Semantic Scholar Title",
            source=PaperSource.SEMANTIC_SCHOLAR,
        )
        result = deduplicator.deduplicate([paper1, paper2])
        merged = result[0]
        assert merged.source == PaperSource.SEMANTIC_SCHOLAR


class TestConvenienceFunction:
    """Test the deduplicate_papers convenience function."""

    def test_deduplicate_papers_function(self) -> None:
        paper1 = create_paper(doi="10.1000/one")
        paper2 = create_paper(doi="10.1000/one")
        paper3 = create_paper(doi="10.1000/two")
        result = deduplicate_papers([paper1, paper2, paper3])
        assert len(result) == 2
        dois = {p.doi for p in result}
        assert dois == {"10.1000/one", "10.1000/two"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])