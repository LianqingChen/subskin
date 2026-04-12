"""Tests for data models: paper.py, trial.py, data_source.py"""

from src.models.paper import Paper, PaperSource, PaperSearchResult
from src.models.trial import ClinicalTrial, TrialPhase, TrialStatus, Intervention, InterventionType
from src.models.data_source import (
    DataSource, 
    DataSourceCategory, 
    DataSourceType, 
    AccessMethod,
    CostModel,
    PriorityLevel,
    CollectionMethod,
)


class TestPaperModel:
    """Test Paper model validation and instantiation."""

    def test_paper_instantiation(self):
        """Test that Paper can be created with required fields."""
        paper = Paper(
            pmid="12345678",
            title="Vitiligo: A review of current treatment options",
            abstract="Vitiligo is an autoimmune disease that causes depigmentation...",
            pub_date="2025-01-15",
            authors=["John Smith", "Jane Doe"],
            journal="Journal of Dermatology",
            source=PaperSource.PUBMED,
        )
        assert paper.pmid == "12345678"
        assert paper.title == "Vitiligo: A review of current treatment options"
        assert "autoimmune" in paper.abstract
        assert paper.pub_date == "2025-01-15"
        assert paper.authors == ["John Smith", "Jane Doe"]
        assert paper.journal == "Journal of Dermatology"
        assert paper.source == PaperSource.PUBMED

    def test_paper_optional_fields(self):
        """Test that optional fields can be None."""
        paper = Paper(
            pmid="12345678",
            title="Test Paper",
            abstract="Test abstract",
            pub_date="2025-01-01",
            authors=[],
            journal="Test Journal",
            source=PaperSource.PUBMED,
        )
        assert paper.chinese_abstract is None
        assert paper.summary is None
        assert paper.mesh_terms == []
        assert paper.keywords == []
        assert paper.doi is None
        assert paper.url is None

    def test_paper_with_optional_fields(self):
        """Test Paper with optional fields provided."""
        paper = Paper(
            pmid="12345678",
            title="Vitiligo treatment with JAK inhibitors",
            abstract="JAK inhibitors show promising results...",
            pub_date="2024-06-01",
            authors=["Alice Brown"],
            journal="New England Journal of Medicine",
            source=PaperSource.PUBMED,
            chinese_abstract="JAK抑制剂治疗白癜风...",
            mesh_terms=["Vitiligo", "JAK Inhibitors", "Therapy"],
            keywords=["vitiligo", "treatment", "JAK"],
            summary="这篇文章总结了JAK抑制剂治疗白癜风的最新进展...",
        )
        assert paper.chinese_abstract is not None
        assert paper.summary is not None
        assert len(paper.mesh_terms) == 3
        assert len(paper.keywords) == 3


class TestTrialModel:
    """Test ClinicalTrial model."""

    def test_trial_instantiation(self):
        """Test that ClinicalTrial can be created with required fields."""
        trial = ClinicalTrial(
            nct_id="NCT01234567",
            title="A Phase 3 Trial of JAK Inhibitor for Vitiligo",
            condition="Vitiligo",
            phase=TrialPhase.PHASE3,
            status=TrialStatus.RECRUITING,
            sponsor="Clinuvel Pharmaceuticals",
            url="https://clinicaltrials.gov/ct2/show/NCT01234567",
        )
        assert trial.nct_id == "NCT01234567"
        assert trial.title == "A Phase 3 Trial of JAK Inhibitor for Vitiligo"
        assert trial.condition == "Vitiligo"
        assert trial.phase == TrialPhase.PHASE3
        assert trial.status == TrialStatus.RECRUITING
        assert trial.sponsor == "Clinuvel Pharmaceuticals"
        assert trial.url == "https://clinicaltrials.gov/ct2/show/NCT01234567"
        assert trial.interventions == []

    def test_trial_with_interventions(self):
        """Test ClinicalTrial with interventions."""
        intervention = Intervention(
            name="Tofacitinib",
            type=InterventionType.DRUG,
            drug_class="JAK inhibitor",
        )
        trial = ClinicalTrial(
            nct_id="NCT01234567",
            title="Test Trial",
            condition="Vitiligo",
            phase=TrialPhase.PHASE2,
            status=TrialStatus.COMPLETED,
            sponsor="Test Sponsor",
            url="https://clinicaltrials.gov/ct2/show/NCT01234567",
            interventions=[intervention],
        )
        assert len(trial.interventions) == 1
        assert trial.interventions[0].drug_class == "JAK inhibitor"


class TestDataSourceModel:
    """Test DataSource model."""

    def test_data_source_instantiation(self):
        """Test DataSource instantiation."""
        ds = DataSource(
            id="pubmed-vitiligo",
            name="PubMed Vitiligo Search",
            category=DataSourceCategory.ENGLISH_RESEARCH,
            url="https://pubmed.ncbi.nlm.nih.gov/",
            type=DataSourceType.COMPREHENSIVE_ACADEMIC_LITERATURE,
            language="en",
            access_method=AccessMethod.API,
            cost=CostModel.FREE,
            data_quality=5,
            priority=PriorityLevel.PRIORITY_1,
            collection_method=CollectionMethod.API_CRAWLING,
        )
        assert ds.id == "pubmed-vitiligo"
        assert ds.name == "PubMed Vitiligo Search"
        assert ds.category == DataSourceCategory.ENGLISH_RESEARCH
        assert ds.url == "https://pubmed.ncbi.nlm.nih.gov/"
        assert ds.cost == CostModel.FREE
        assert ds.data_quality == 5
        assert ds.priority == PriorityLevel.PRIORITY_1
        assert ds.collection_method == CollectionMethod.API_CRAWLING
        assert ds.is_active is True

    def test_data_source_inactive(self):
        """Test inactive data source."""
        ds = DataSource(
            id="old-source",
            name="Old Source",
            category=DataSourceCategory.ENGLISH_RESEARCH,
            url="https://example.com",
            type=DataSourceType.COMPREHENSIVE_ACADEMIC_LITERATURE,
            language="en",
            access_method=AccessMethod.WEB_SCRAPING,
            cost=CostModel.FREE,
            data_quality=3,
            priority=PriorityLevel.PRIORITY_3,
            collection_method=CollectionMethod.WEB_SCRAPING,
            is_active=False,
        )
        assert ds.is_active is False
