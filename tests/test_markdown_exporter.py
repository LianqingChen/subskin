import json
from datetime import datetime
from pathlib import Path

import pytest
from src.exporters.markdown_exporter import MarkdownExporter
from src.models.paper import Paper, PaperSource
from src.models.trial import ClinicalTrial, TrialPhase, TrialStatus


def test_markdown_exporter_init(tmp_path: Path):
    exp = MarkdownExporter(export_dir=tmp_path)
    assert exp.export_dir == tmp_path


def test_export_paper_minimal_and_disclaimer(tmp_path: Path):
    exporter = MarkdownExporter(export_dir=tmp_path)
    p = Paper(title="Minimal Paper", source=PaperSource.PUBMED)
    out = exporter.export_paper(
        p, filename="minimal_paper.md", date=datetime(2026, 4, 11)
    )
    text = out.read_text(encoding="utf-8")
    assert out.name == "minimal_paper.md"
    assert text.startswith("# Minimal Paper")
    assert "免责声明" in text


def test_export_papers_multiple_and_disclaimer(tmp_path: Path):
    exporter = MarkdownExporter(export_dir=tmp_path)
    p1 = Paper(title="First Paper", source=PaperSource.PUBMED, pmid="1", authors=["A"])
    p2 = Paper(
        title="Second Paper",
        source=PaperSource.SEMANTIC_SCHOLAR,
        doi="10.1/abc",
        authors=["B"],
    )

    out_paths = exporter.export_papers([p1, p2], date=datetime(2026, 4, 11))
    assert len(out_paths) == 2
    for p in out_paths:
        text = p.read_text(encoding="utf-8")
        assert text.startswith("# ")
        assert "免责声明" in text


def test_paper_frontmatter_yaml_generation(tmp_path: Path):
    exporter = MarkdownExporter(export_dir=tmp_path)
    paper = Paper(title="Demo Paper", source=PaperSource.PUBMED, pmid="999")
    frontmatter = exporter._paper_to_frontmatter(paper)
    import yaml

    yaml_str = yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False)
    assert "title" in yaml_str
    assert frontmatter["title"] == "Demo Paper"


def test_paper_markdown_content_formatting(tmp_path: Path):
    exporter = MarkdownExporter(export_dir=tmp_path)
    paper = Paper(
        title="Formatting Paper",
        source=PaperSource.PUBMED,
        pmid="8888",
        authors=["Alice"],
        abstract="Abstract",
        summary="Summary",
    )
    content = exporter._paper_to_markdown_content(paper)
    assert content.startswith("# Formatting Paper")
    assert "摘要（英文）" in content or "患者友好总结" in content


def test_trial_markdown_formatting(tmp_path: Path):
    exporter = MarkdownExporter(export_dir=tmp_path)
    trial = ClinicalTrial(
        nct_id="NCT00000002",
        title="Vitiligo Trial 2",
        condition="Vitiligo",
        phase=TrialPhase.PHASE2,
        status=TrialStatus.RECRUITING,
        sponsor="SponsorY",
        url="https://clinicaltrials.gov/ct2/show/NCT00000002",
    )
    md = exporter._trial_to_markdown(trial)
    assert md.startswith("# Vitiligo Trial 2")
    assert "NCT ID" in md


def test_export_deduplicated_papers_index_exists(tmp_path: Path):
    exporter = MarkdownExporter(export_dir=tmp_path)
    p1 = Paper(title="Paper A", source=PaperSource.PUBMED, pmid="A1")
    p2 = Paper(title="Paper B", source=PaperSource.PUBMED, pmid="A2")
    out_dir = exporter.export_deduplicated_papers([p1, p2], date=datetime(2026, 4, 11))
    index_path = out_dir / "README.md"
    assert index_path.exists()
    text = index_path.read_text(encoding="utf-8")
    assert "去重论文合集" in text
    assert "免责声明" in text
