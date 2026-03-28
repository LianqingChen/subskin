"""Tests for exporters module."""
from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from src.models.paper import Paper, PaperSource
from src.exporters.json_exporter import JSONExporter
from src.exporters.markdown_exporter import MarkdownExporter


@pytest.fixture
def sample_paper() -> Paper:
    return Paper(
        pmid="12345678",
        title="Test Paper on Vitiligo",
        abstract="This is a test abstract about vitiligo treatment.",
        authors=["Author One", "Author Two"],
        journal="Test Journal of Dermatology",
        pub_date="2024-03-01",
        source=PaperSource.PUBMED,
        crawled_at=datetime.now(),
        chinese_abstract="这是关于白癜风治疗的测试摘要。",
        summary="本文研究了白癜风的新型治疗方法，患者应在医生指导下使用。",
        translated=True,
        summarized=True,
        citation_count=25,
        mesh_terms=["Vitiligo", "Therapeutics"],
        keywords=["vitiligo", "treatment", "JAK inhibitors"],
        language="en",
    )


@pytest.fixture
def sample_paper_minimal() -> Paper:
    return Paper(
        title="Minimal Test Paper",
        abstract="Minimal abstract.",
        authors=[],
        source=PaperSource.SEMANTIC_SCHOLAR,
        crawled_at=datetime.now(),
    )


class TestJSONExporter:
    def test_export_papers_basic(self, sample_paper, tmp_path):
        exporter = JSONExporter(export_dir=tmp_path / "exports")
        papers = [sample_paper]
        
        output_path = exporter.export_papers(papers, filename="test.json")
        
        assert output_path.exists()
        assert output_path.name == "test.json"
        
        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        assert len(data) == 1
        assert data[0]["title"] == sample_paper.title
        assert data[0]["pmid"] == sample_paper.pmid
        assert data[0]["chinese_abstract"] == sample_paper.chinese_abstract
        assert data[0]["summary"] == sample_paper.summary
    
    def test_export_papers_without_filename(self, sample_paper, tmp_path):
        exporter = JSONExporter(export_dir=tmp_path / "exports")
        papers = [sample_paper]
        
        output_path = exporter.export_papers(papers)
        
        assert output_path.exists()
        assert output_path.suffix == ".json"
        assert "papers_" in output_path.name
    
    def test_export_papers_multiple(self, sample_paper, sample_paper_minimal, tmp_path):
        exporter = JSONExporter(export_dir=tmp_path / "exports")
        papers = [sample_paper, sample_paper_minimal]
        
        output_path = exporter.export_papers(papers, filename="multi.json")
        
        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        assert len(data) == 2
        titles = {p["title"] for p in data}
        assert "Test Paper on Vitiligo" in titles
        assert "Minimal Test Paper" in titles
    
    def test_export_deduplicated_papers(self, sample_paper, sample_paper_minimal, tmp_path):
        exporter = JSONExporter(export_dir=tmp_path / "exports")
        papers = [sample_paper, sample_paper_minimal]
        
        output_path = exporter.export_deduplicated_papers(
            papers, source_info="test_source"
        )
        
        assert output_path.exists()
        
        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        assert "metadata" in data
        assert "papers" in data
        assert data["metadata"]["paper_count"] == 2
        assert data["metadata"]["source_info"] == "test_source"
        assert data["metadata"]["deduplicated"] is True
    
    def test_serialize_paper_handles_datetime(self, sample_paper, tmp_path):
        exporter = JSONExporter(export_dir=tmp_path / "exports")
        papers = [sample_paper]
        
        output_path = exporter.export_papers(papers, filename="datetime_test.json")
        
        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        paper_data = data[0]
        assert "crawled_at" in paper_data
        assert isinstance(paper_data["crawled_at"], str)
        # Should be ISO format
        assert "T" in paper_data["crawled_at"] or " " in paper_data["crawled_at"]
    
    def test_export_to_date_directory(self, sample_paper, tmp_path):
        export_dir = tmp_path / "exports"
        exporter = JSONExporter(export_dir=export_dir)
        
        test_date = datetime(2024, 3, 15)
        output_path = exporter.export_papers(
            [sample_paper], filename="test.json", date=test_date
        )
        
        expected_dir = export_dir / "2024-03-15"
        assert output_path.parent == expected_dir
        assert expected_dir.exists()


class TestMarkdownExporter:
    def test_export_paper_basic(self, sample_paper, tmp_path):
        exporter = MarkdownExporter(export_dir=tmp_path / "exports")
        
        output_path = exporter.export_paper(sample_paper, filename="test.md")
        
        assert output_path.exists()
        assert output_path.suffix == ".md"
        
        content = output_path.read_text(encoding="utf-8")
        assert content.startswith("---\n")
        assert "---\n\n" in content  # Frontmatter separator
        
        # Check sections
        assert "# Test Paper on Vitiligo" in content
        assert "## 摘要（英文）" in content
        assert "## 摘要（中文）" in content
        assert "## 患者友好总结" in content
        assert "免责声明" in content
    
    def test_export_paper_minimal(self, sample_paper_minimal, tmp_path):
        exporter = MarkdownExporter(export_dir=tmp_path / "exports")
        
        output_path = exporter.export_paper(sample_paper_minimal)
        
        content = output_path.read_text(encoding="utf-8")
        assert "# Minimal Test Paper" in content
        # Should not have Chinese sections since fields are None
        assert "## 摘要（中文）" not in content
        assert "## 患者友好总结" not in content
    
    def test_export_papers_batch(self, sample_paper, sample_paper_minimal, tmp_path):
        exporter = MarkdownExporter(export_dir=tmp_path / "exports")
        papers = [sample_paper, sample_paper_minimal]
        
        output_paths = exporter.export_papers(papers, base_filename="batch")
        
        assert len(output_paths) == 2
        assert all(p.exists() for p in output_paths)
        assert output_paths[0].name == "batch_001.md"
        assert output_paths[1].name == "batch_002.md"
        
        # Verify content differences
        content1 = output_paths[0].read_text(encoding="utf-8")
        content2 = output_paths[1].read_text(encoding="utf-8")
        assert "Test Paper on Vitiligo" in content1
        assert "Minimal Test Paper" in content2
    
    def test_export_deduplicated_papers(self, sample_paper, sample_paper_minimal, tmp_path):
        exporter = MarkdownExporter(export_dir=tmp_path / "exports")
        papers = [sample_paper, sample_paper_minimal]
        
        output_dir = exporter.export_deduplicated_papers(
            papers, collection_name="test_collection"
        )
        
        assert output_dir.exists()
        assert output_dir.is_dir()
        assert "deduplicated_papers_test_collection" in output_dir.name
        
        # Check for individual paper files
        paper_files = list(output_dir.glob("paper_*.md"))
        assert len(paper_files) == 2
        
        # Check for README
        readme_path = output_dir / "README.md"
        assert readme_path.exists()
        readme_content = readme_path.read_text(encoding="utf-8")
        assert "# 去重论文合集" in readme_content
        assert "论文数量" in readme_content
    
    def test_frontmatter_includes_all_fields(self, sample_paper, tmp_path):
        exporter = MarkdownExporter(export_dir=tmp_path / "exports")
        
        output_path = exporter.export_paper(sample_paper, filename="frontmatter_test.md")
        content = output_path.read_text(encoding="utf-8")
        
        # Extract frontmatter (between --- and ---)
        lines = content.split("\n")
        frontmatter_start = lines.index("---")
        frontmatter_end = lines.index("---", frontmatter_start + 1)
        frontmatter_lines = lines[frontmatter_start + 1:frontmatter_end]
        frontmatter_text = "\n".join(frontmatter_lines)
        
        # Check key fields
        assert "title:" in frontmatter_text
        assert "authors:" in frontmatter_text
        assert "journal:" in frontmatter_text
        assert "pmid:" in frontmatter_text
        assert "doi:" not in frontmatter_text  # This paper has no DOI
        assert "source:" in frontmatter_text
        assert "crawled_at:" in frontmatter_text
    
    def test_disclaimer_present(self, sample_paper, tmp_path):
        exporter = MarkdownExporter(export_dir=tmp_path / "exports")
        
        output_path = exporter.export_paper(sample_paper)
        content = output_path.read_text(encoding="utf-8")
        
        assert "免责声明" in content
        assert "本文不构成医疗建议" in content
    
    def test_export_to_date_directory(self, sample_paper, tmp_path):
        export_dir = tmp_path / "exports"
        exporter = MarkdownExporter(export_dir=export_dir)
        
        test_date = datetime(2024, 3, 20)
        output_path = exporter.export_paper(
            sample_paper, filename="test.md", date=test_date
        )
        
        expected_dir = export_dir / "2024-03-20"
        assert output_path.parent == expected_dir
        assert expected_dir.exists()


def test_exporters_module_imports():
    """Test that exporters module can be imported correctly."""
    from src.exporters import JSONExporter, MarkdownExporter
    
    assert JSONExporter is not None
    assert MarkdownExporter is not None
    
    # Verify they have expected methods
    assert hasattr(JSONExporter, "export_papers")
    assert hasattr(JSONExporter, "export_deduplicated_papers")
    assert hasattr(MarkdownExporter, "export_paper")
    assert hasattr(MarkdownExporter, "export_papers")