import pytest
from pydantic import ValidationError

from src.models.data_source import (
    DataSource,
    DataSourceCategory,
    DataSourceType,
    AccessMethod,
    CostModel,
    PriorityLevel,
    CollectionMethod,
    DataSourceCategoryInfo,
    PriorityGroup,
    CollectionStrategy,
    QualityStandard,
)


def test_datasource_enums_and_validation():
    ds = DataSource(
        id="ds1",
        name="PubMed",
        category=DataSourceCategory.ENGLISH_RESEARCH,
        url="https://pubmed.ncbi.nlm.nih.gov/",
        type=DataSourceType.BIOMEDICAL_LITERATURE,
        language="en",
        access_method=AccessMethod.API,
        cost=CostModel.FREE,
        data_quality=5,
        priority=PriorityLevel.PRIORITY_1,
        collection_method=CollectionMethod.API_CRAWLING,
        api_endpoint="https://api.pubmed.example/",
        rate_limit=10,
        search_terms=["vitiligo"],
        estimated_volume=1000,
        file_format="json",
        ethical_considerations=["consent"],
        notes="note",
        last_verified="2025-01-01",
        is_active=True,
    )

    assert ds.should_use_rate_limiting() is True
    assert ds.get_collection_tools()  # non-empty list
    assert ds.requires_ethical_considerations() is False
    assert ds.to_dict()["name"] == "PubMed"


def test_datasource_validation_and_edge_cases():
    # invalid URL should raise
    with pytest.raises(ValidationError):
        DataSource(
            id="ds2",
            name="BadURLSource",
            category=DataSourceCategory.CHINESE_RESEARCH,
            url="ftp://example.com",
            type=DataSourceType.BIOMEDICAL_LITERATURE,
            language="en",
            access_method=AccessMethod.WEB_BROWSING,
            cost=CostModel.FREE,
            data_quality=3,
            priority=PriorityLevel.PRIORITY_2,
            collection_method=CollectionMethod.WEB_SCRAPING,
        )

    # invalid data quality
    with pytest.raises(ValidationError):
        DataSource(
            id="ds3",
            name="BadQuality",
            category=DataSourceCategory.GUIDELINES,
            url="https://example.com",
            type=DataSourceType.MEDICAL_JOURNAL,
            language="en",
            access_method=AccessMethod.API,
            cost=CostModel.FREE,
            data_quality=6,  # out of range
            priority=PriorityLevel.PRIORITY_3,
            collection_method=CollectionMethod.API_CRAWLING,
        )

    # color validation on category info
    with pytest.raises(ValidationError):
        DataSourceCategoryInfo(
            id="cat1",
            name="Category",
            description="desc",
            color="not-a-color",
        )


def test_placeholder_models_exist():
    PriorityGroup(name="Group A", description="desc", data_sources=["ds1"])  # type: ignore
    CollectionStrategy(id="strat1", description="desc", recommended_tools=["tool1"])  # type: ignore
    QualityStandard(
        source_credibility=["credible"],
        content_validation=["validate"],
        data_cleaning=["clean"],
        privacy_protection=["privacy"],
    )
