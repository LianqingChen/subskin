from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterator

import pytest

from src.models.paper import Paper, PaperSource
from src.models.trial import (
    ClinicalTrial,
    Intervention,
    InterventionType,
    Location,
    TrialPhase,
    TrialStatus,
)


@pytest.fixture
def temp_cache_db(tmp_path: Path) -> Iterator[Path]:
    db_path = tmp_path / "cache.sqlite3"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT)"
        )
        connection.commit()

    yield db_path


class MockAPIResponse:
    def __init__(self, json_data: dict[str, object], status_code: int = 200) -> None:
        self._json_data = json_data
        self.status_code = status_code
        self.text = str(json_data)
        self.content = self.text.encode("utf-8")

    def json(self) -> dict[str, object]:
        return self._json_data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise ValueError(f"HTTP {self.status_code}")


@pytest.fixture
def mock_api_response() -> Iterator[MockAPIResponse]:
    yield MockAPIResponse(
        {
            "status": "ok",
            "results": [],
        }
    )


@pytest.fixture
def sample_paper() -> Paper:
    return Paper(
        pmid="12345678",
        doi="10.1000/example.doi",
        title="Vitiligo treatment overview",
        abstract="Sample abstract for testing.",
        authors=["Alice Zhang", "Bob Li"],
        journal="Journal of Vitiligo Research",
        pub_date="2026-03-01",
        mesh_terms=["Vitiligo", "Therapeutics"],
        keywords=["vitiligo", "treatment"],
        source=PaperSource.PUBMED,
        url="https://pubmed.ncbi.nlm.nih.gov/12345678/",
        citation_count=12,
    )


@pytest.fixture
def sample_trial() -> ClinicalTrial:
    return ClinicalTrial(
        nct_id="NCT01234567",
        title="Study of a JAK inhibitor for vitiligo",
        condition="Vitiligo",
        interventions=[
            Intervention(
                name="JAK inhibitor",
                type=InterventionType.DRUG,
                description="Oral treatment",
                drug_class="JAK inhibitor",
                dosage="10 mg twice daily",
                route="oral",
            )
        ],
        phase=TrialPhase.PHASE2,
        status=TrialStatus.RECRUITING,
        enrollment=120,
        sponsor="Example Hospital",
        collaborators=["Example University"],
        start_date="2026-01",
        completion_date="2027-12",
        last_update_date="2026-03-01",
        locations=[
            Location(
                facility="Example Hospital",
                city="Shanghai",
                country="China",
                status="Recruiting",
            )
        ],
        url="https://clinicaltrials.gov/ct2/show/NCT01234567",
        publication_urls=["https://pubmed.ncbi.nlm.nih.gov/12345678/"],
        study_type="INTERVENTIONAL",
        primary_outcome="Change in repigmentation",
        secondary_outcome="Safety and tolerability",
        inclusion_criteria="Adults with non-segmental vitiligo",
        exclusion_criteria="Recent systemic therapy",
    )
