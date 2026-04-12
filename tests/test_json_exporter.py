import json
from datetime import datetime
from pathlib import Path
import pytest

from src.exporters.json_exporter import JSONExporter
from src.models.paper import Paper, PaperSource
from src.models.trial import ClinicalTrial, TrialPhase, TrialStatus


def test_json_exporter_init(tmp_path: Path):
    exp = JSONExporter(export_dir=tmp_path)
    assert exp.export_dir == tmp_path


def test_export_papers_with_sample_papers(tmp_path: Path):
    exporter = JSONExporter(export_dir=tmp_path)
    p1 = Paper(title="Test Paper 1", source=PaperSource.PUBMED)
    p2 = Paper(
        title="Test Paper 2",
        source=PaperSource.SEMANTIC_SCHOLAR,
        pmid="1234",
        authors=["Alice"],
    )

    out_path = exporter.export_papers(
        [p1, p2], date=datetime(2026, 4, 11), filename="papers.json"
    )
    assert out_path.name == "papers.json"
    assert "2026-04-11" in str(out_path.parent)

    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert isinstance(data, list) and len(data) == 2
    assert "title" in data[0]
    assert "source" in data[0]
    assert "crawled_at" in data[0]


def test_export_trials_with_sample_trials(tmp_path: Path):
    exporter = JSONExporter(export_dir=tmp_path)
    trial = ClinicalTrial(
        nct_id="NCT00000001",
        title="Vitiligo Trial",
        condition="Vitiligo",
        phase=TrialPhase.PHASE1,
        status=TrialStatus.RECRUITING,
        sponsor="SponsorX",
        url="https://example.org/ct2/show/NCT00000001",
    )

    out_path = exporter.export_trials(
        [trial], date=datetime(2026, 4, 11), filename="trials.json"
    )
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert data[0]["nct_id"] == "NCT00000001"
    assert data[0]["title"] == "Vitiligo Trial"


def test_export_deduplicated_papers(tmp_path: Path):
    exporter = JSONExporter(export_dir=tmp_path)
    p1 = Paper(title="Paper One", source=PaperSource.PUBMED)
    p2 = Paper(title="Paper Two", source=PaperSource.SEMANTIC_SCHOLAR, pmid="111")

    out_path = exporter.export_deduplicated_papers([p1, p2], date=datetime(2026, 4, 11))
    date_dir = tmp_path / "2026-04-11"
    files = list(date_dir.glob("deduplicated_papers*.json"))
    assert len(files) == 1

    data = json.loads(files[0].read_text(encoding="utf-8"))
    assert "metadata" in data and "papers" in data
    assert data["metadata"].get("deduplicated") is True
    assert len(data["papers"]) == 2
