import pytest
from pydantic import ValidationError

from src.models.paper import Paper, PaperUpdate, PaperSearchResult, PaperSource


def test_paper_valid_minimal_required_fields():
    p = Paper(
        title="Vitiligo study",
        source=PaperSource.PUBMED,
    )
    assert p.title == "Vitiligo study"
    assert p.source == PaperSource.PUBMED
    # defaults
    assert p.authors == []
    assert p.mesh_terms == []


def test_paper_full_valid_data_and_methods():
    p = Paper(
        pmid="12345",
        doi="10.1000/xyz",
        title="A study on vitiligo treatments",
        abstract="Abstract text",
        authors=["Alice", "Bob", "Carol", "Dave"],
        journal="Journal of Vitiligo",
        pub_date="2020-12-31",
        mesh_terms=["Melanocytes"],
        keywords=["vitiligo", "treatment"],
        source=PaperSource.PUBMED,
        url="http://example.org/paper",
        citation_count=5,
        language="en",
        chinese_abstract="中文摘要",
        summary="Patient-friendly summary",
        translated=True,
        summarized=True,
    )

    # get_citation should include first three authors and year, and journal
    cit = p.get_citation()
    assert cit.startswith("Alice, Bob, Carol et al.")
    assert "(2020)" in cit
    assert "A study on vitiligo treatments" in cit
    assert "Journal" in cit

    d = p.to_dict()
    assert isinstance(d, dict)
    ids = p.get_identifiers()
    assert ids["pmid"] == "12345"
    assert ids["doi"] == "10.1000/xyz"
    assert ids["url"] == "http://example.org/paper"
    assert p.is_complete()


def test_paper_validation_and_optional_none_fields():
    # optional url, doi, pmid can be None but title and source are required
    p = Paper(title="Only required", source=PaperSource.OTHER)
    assert p.title == "Only required"
    assert p.source == PaperSource.OTHER
    assert p.get_identifiers() == {}
    assert p.is_complete() is False


def test_paper_invalid_data_raises_validation_error():
    with pytest.raises(ValidationError):
        Paper(title="Test", source="not-a-valid-source")  # type: ignore[arg-type]


def test_paper_missing_required_fields_raises():
    with pytest.raises(ValidationError):
        Paper()


def test_paper_update_and_search_result_models():
    u = PaperUpdate(title="Updated title", summarized=True)
    s = PaperSearchResult(
        paper=Paper(title="X", source=PaperSource.SEMANTIC_SCHOLAR),
        relevance_score=0.85,
    )
    assert isinstance(u, PaperUpdate)
    assert isinstance(s, PaperSearchResult)
