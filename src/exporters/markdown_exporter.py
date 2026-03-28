import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
import yaml
from src.models.paper import Paper
from src.models.trial import ClinicalTrial

logger = logging.getLogger(__name__)


class MarkdownExporter:
    def __init__(self, export_dir: Optional[Path] = None):
        self.export_dir = export_dir or Path("data/exports")
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def _get_date_dir(self, date: Optional[datetime] = None) -> Path:
        if date is None:
            date = datetime.now()
        date_str = date.strftime("%Y-%m-%d")
        return self.export_dir / date_str

    def _paper_to_frontmatter(self, paper: Paper) -> Dict[str, Any]:
        frontmatter = {
            "title": paper.title,
            "date": paper.pub_date or datetime.now().strftime("%Y-%m-%d"),
            "source": paper.source.value
            if hasattr(paper.source, "value")
            else paper.source,
            "authors": paper.authors,
            "journal": paper.journal,
            "pmid": paper.pmid,
            "doi": paper.doi,
            "url": paper.url,
            "crawled_at": paper.crawled_at.isoformat() if paper.crawled_at else None,
            "citation_count": paper.citation_count,
            "mesh_terms": paper.mesh_terms,
            "keywords": paper.keywords,
            "language": paper.language,
            "translated": paper.translated,
            "summarized": paper.summarized,
        }
        # Remove None values
        return {k: v for k, v in frontmatter.items() if v is not None}

    def _paper_to_markdown_content(self, paper: Paper) -> str:
        sections = []

        # Title as heading
        sections.append(f"# {paper.title}\n")

        # Authors and journal
        if paper.authors:
            authors_str = ", ".join(paper.authors)
            sections.append(f"**作者**: {authors_str}\n")

        if paper.journal:
            sections.append(f"**期刊**: {paper.journal}\n")

        if paper.pub_date:
            sections.append(f"**发表日期**: {paper.pub_date}\n")

        # Identifiers
        identifiers = []
        if paper.pmid:
            identifiers.append(f"PMID: {paper.pmid}")
        if paper.doi:
            identifiers.append(f"DOI: {paper.doi}")
        if paper.url:
            identifiers.append(f"URL: {paper.url}")

        if identifiers:
            sections.append(f"**标识符**: {' | '.join(identifiers)}\n")

        # Abstract section
        if paper.abstract:
            sections.append("## 摘要（英文）\n")
            sections.append(f"{paper.abstract}\n")

        # Chinese abstract section
        if paper.chinese_abstract:
            sections.append("## 摘要（中文）\n")
            sections.append(f"{paper.chinese_abstract}\n")

        # Summary section (patient-friendly)
        if paper.summary:
            sections.append("## 患者友好总结\n")
            sections.append(f"{paper.summary}\n")

        # Keywords and MeSH terms
        if paper.keywords:
            sections.append(f"**关键词**: {', '.join(paper.keywords)}\n")

        if paper.mesh_terms:
            sections.append(f"**MeSH术语**: {', '.join(paper.mesh_terms)}\n")

        # Metadata
        if paper.citation_count is not None:
            sections.append(f"**引用次数**: {paper.citation_count}\n")

        sections.append(
            f"**来源**: {paper.source.value if hasattr(paper.source, 'value') else paper.source}\n"
        )
        sections.append(
            f"**抓取时间**: {paper.crawled_at.isoformat() if paper.crawled_at else '未知'}\n"
        )

        # Disclaimer
        sections.append("\n---\n")
        sections.append(
            "> **免责声明**: 本文不构成医疗建议。所有内容仅供参考，具体治疗方案请咨询专业医生。\n"
        )

        return "\n".join(sections)

    def _paper_to_markdown(self, paper: Paper) -> str:
        frontmatter = self._paper_to_frontmatter(paper)
        content = self._paper_to_markdown_content(paper)

        yaml_frontmatter = yaml.dump(
            frontmatter, allow_unicode=True, default_flow_style=False
        )

        return f"---\n{yaml_frontmatter}---\n\n{content}"

    def _trial_to_markdown(self, trial: ClinicalTrial) -> str:
        # Simplified trial markdown export
        frontmatter = {
            "title": trial.title,
            "nct_id": trial.nct_id,
            "condition": trial.condition,
            "phase": trial.phase,
            "status": trial.status,
            "enrollment": trial.enrollment,
            "sponsor": trial.sponsor,
            "start_date": trial.start_date,
            "completion_date": trial.completion_date,
            "crawled_at": trial.crawled_at.isoformat() if trial.crawled_at else None,
            "url": trial.url,
        }
        frontmatter = {k: v for k, v in frontmatter.items() if v is not None}

        content = [
            f"# {trial.title}\n",
            f"**NCT ID**: {trial.nct_id}",
            f"**适应症**: {trial.condition}",
            f"**阶段**: {trial.phase}",
            f"**状态**: {trial.status}",
            f"**计划入组人数**: {trial.enrollment}",
            f"**申办方**: {trial.sponsor}",
            f"**开始日期**: {trial.start_date}",
            f"**完成日期**: {trial.completion_date}",
            f"**地点**: {', '.join(trial.locations) if trial.locations else '未指定'}",
            "\n---\n",
            "> **免责声明**: 本文不构成医疗建议。所有内容仅供参考，具体治疗方案请咨询专业医生。\n",
        ]

        yaml_frontmatter = yaml.dump(
            frontmatter, allow_unicode=True, default_flow_style=False
        )
        return f"---\n{yaml_frontmatter}---\n\n" + "\n".join(content)

    def export_paper(
        self,
        paper: Paper,
        filename: Optional[str] = None,
        date: Optional[datetime] = None,
    ) -> Path:
        date_dir = self._get_date_dir(date)
        date_dir.mkdir(parents=True, exist_ok=True)

        if filename is None:
            # Create filename from paper title and identifiers
            identifier = paper.pmid or paper.doi or "paper"
            safe_title = "".join(c if c.isalnum() else "_" for c in paper.title[:50])
            filename = f"{safe_title}_{identifier}.md"

        output_path = date_dir / filename

        markdown_content = self._paper_to_markdown(paper)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        logger.info(f"Exported paper '{paper.title}' to {output_path}")
        return output_path

    def export_papers(
        self,
        papers: List[Paper],
        base_filename: Optional[str] = None,
        date: Optional[datetime] = None,
    ) -> List[Path]:
        date_dir = self._get_date_dir(date)
        date_dir.mkdir(parents=True, exist_ok=True)

        output_paths = []

        for i, paper in enumerate(papers):
            if base_filename:
                filename = f"{base_filename}_{i + 1:03d}.md"
            else:
                identifier = paper.pmid or paper.doi or f"paper_{i + 1:03d}"
                safe_title = "".join(
                    c if c.isalnum() else "_" for c in paper.title[:30]
                )
                filename = f"{safe_title}_{identifier}.md"

            output_path = date_dir / filename
            markdown_content = self._paper_to_markdown(paper)

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)

            output_paths.append(output_path)

        logger.info(f"Exported {len(papers)} papers to {date_dir}")
        return output_paths

    def export_deduplicated_papers(
        self,
        papers: List[Paper],
        collection_name: Optional[str] = None,
        date: Optional[datetime] = None,
    ) -> Path:
        date_dir = self._get_date_dir(date)
        date_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        collection_suffix = f"_{collection_name}" if collection_name else ""
        dir_name = f"deduplicated_papers{collection_suffix}_{timestamp}"

        output_dir = date_dir / dir_name
        output_dir.mkdir(parents=True, exist_ok=True)

        # Export each paper individually into the collection directory
        output_paths = []
        for i, paper in enumerate(papers):
            filename = f"paper_{i + 1:03d}.md"
            output_path = output_dir / filename
            markdown_content = self._paper_to_markdown(paper)

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)

            output_paths.append(output_path)

        logger.info(f"Exported {len(papers)} papers to {output_dir}")

        # Create index file
        index_content = [
            f"# 去重论文合集\n",
            f"**导出时间**: {datetime.now().isoformat()}\n",
            f"**论文数量**: {len(papers)}\n",
            f"**合集名称**: {collection_name or '未命名'}\n\n",
            "## 论文列表\n",
        ]

        for i, paper in enumerate(papers, 1):
            identifier = paper.pmid or paper.doi or f"paper_{i}"
            safe_title = paper.title.replace("|", "\\|")
            index_content.append(
                f"{i}. [{safe_title}](paper_{i:03d}.md) - {identifier}\n"
            )

        index_content.append("\n---\n")
        index_content.append(
            "> **免责声明**: 本文不构成医疗建议。所有内容仅供参考，具体治疗方案请咨询专业医生。\n"
        )

        index_path = output_dir / "README.md"
        with open(index_path, "w", encoding="utf-8") as f:
            f.write("".join(index_content))

        logger.info(f"Exported {len(papers)} deduplicated papers to {output_dir}")
        return output_dir
