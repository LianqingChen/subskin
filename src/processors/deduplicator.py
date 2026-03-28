"""Data deduplication module for SubSkin project.

This module provides a :class:`Deduplicator` that merges paper records from
multiple sources (PubMed, Semantic Scholar) by their unique identifiers (DOI, PMID)
and intelligently merges metadata while tracking source provenance.

Example::

    from src.processors.deduplicator import Deduplicator

    deduplicator = Deduplicator()
    papers = [paper1, paper2, paper3]  # from multiple sources
    deduplicated = deduplicator.deduplicate(papers)
"""

from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

from src.models.paper import Paper, PaperSource

logger = logging.getLogger(__name__)


class Deduplicator:
    """Deduplicates and merges paper records from multiple sources.

    Handles papers from PubMed, Semantic Scholar, and other sources by:
    1. Grouping papers by their unique identifiers (DOI > PMID > title+author hash)
    2. Merging metadata within each group
    3. Preserving source attribution at field level (if enabled)

    Args:
        enable_field_source_tracking: If True, track which source provided
            each field in merged papers. Defaults to False for now.
        prefer_source_order: Order of source preference for conflicting data.
            Earlier sources are preferred.
        fuzzy_title_similarity_threshold: Threshold for title similarity (0-1)
            when using fuzzy matching as fallback. Default 0.85.
    """

    DEFAULT_PREFER_SOURCE_ORDER = [PaperSource.PUBMED, PaperSource.SEMANTIC_SCHOLAR]

    def __init__(
        self,
        enable_field_source_tracking: bool = False,
        prefer_source_order: Optional[List[PaperSource]] = None,
        fuzzy_title_similarity_threshold: float = 0.85,
    ) -> None:
        self.enable_field_source_tracking = enable_field_source_tracking
        self.prefer_source_order = prefer_source_order or self.DEFAULT_PREFER_SOURCE_ORDER
        self.fuzzy_threshold = fuzzy_title_similarity_threshold

    def deduplicate(self, papers: List[Paper]) -> List[Paper]:
        """Deduplicate list of papers, merging those with same identifier.

        Process:
        1. Group papers by primary key (DOI > PMID > title+author hash)
        2. Within each group, merge papers into single unified paper
        3. Return list of merged papers

        Args:
            papers: List of Paper objects, potentially from multiple sources
                with duplicates.

        Returns:
            List of deduplicated Paper objects.
        """
        if not papers:
            return []

        logger.info(f"Deduplicating {len(papers)} papers from {len(set(p.source for p in papers))} sources")

        groups = self._group_by_primary_key(papers)
        merged_papers: List[Paper] = []
        
        for key, group_papers in groups.items():
            if len(group_papers) == 1:
                merged_papers.append(group_papers[0])
                continue

            merged_paper = self._merge_paper_group(group_papers)
            merged_papers.append(merged_paper)
            logger.debug(f"Merged {len(group_papers)} papers with key {key}")

        logger.info(f"Deduplicated {len(papers)} → {len(merged_papers)} papers")
        return merged_papers

    def _group_by_primary_key(self, papers: List[Paper]) -> Dict[str, List[Paper]]:
        """Group papers by their primary identifier.

        Primary key hierarchy:
        1. DOI (most reliable, globally unique)
        2. PMID (if DOI unavailable)
        3. Title + first author + year hash (fallback for fuzzy matching)

        Returns:
            Dict mapping primary key to list of papers with that key.
        """
        groups: Dict[str, List[Paper]] = defaultdict(list)

        for paper in papers:
            key = self._get_primary_key(paper)
            groups[key].append(paper)

        return dict(groups)

    def _get_primary_key(self, paper: Paper) -> str:
        """Get primary key for a paper.

        Priority: DOI > PMID > title+first_author+year hash

        Args:
            paper: Paper object

        Returns:
            String key for grouping.
        """
        if paper.doi:
            return f"doi:{paper.doi.lower().strip()}"
        if paper.pmid:
            return f"pmid:{paper.pmid.strip()}"

        # Fallback fuzzy key based on title, first author, and year
        first_author = paper.authors[0] if paper.authors else ""
        year = paper.pub_date[:4] if paper.pub_date and len(paper.pub_date) >= 4 else ""
        title_normalized = paper.title.lower().strip()[:100]
        hash_input = f"{title_normalized}|{first_author}|{year}"
        hash_key = hashlib.md5(hash_input.encode()).hexdigest()[:16]
        return f"hash:{hash_key}"

    def _merge_paper_group(self, papers: List[Paper]) -> Paper:
        """Merge a group of papers representing the same publication.

        Args:
            papers: List of Paper objects representing same publication
                (same DOI/PMID or fuzzy match).

        Returns:
            Single merged Paper object.
        """
        if len(papers) == 1:
            return papers[0]

        # Sort by source preference (PubMed > Semantic Scholar > others)
        sorted_papers = sorted(
            papers,
            key=lambda p: (
                self.prefer_source_order.index(p.source)
                if p.source in self.prefer_source_order
                else len(self.prefer_source_order)
            ),
        )

        # Start with most preferred paper as base
        base_paper = sorted_papers[0]

        # Merge all papers into base
        for paper in sorted_papers[1:]:
            base_paper = self._merge_two_papers(base_paper, paper)

        # Update source field to indicate merged status
        sources = list(set(p.source for p in papers))
        if len(sources) > 1:
            # If merged from multiple sources, mark as "merged"
            # Could create a new PaperSource value like "MERGED"
            pass  # Keep original source for now, or update metadata

        return base_paper

    def _merge_two_papers(self, paper1: Paper, paper2: Paper) -> Paper:
        """Merge two Paper objects, with paper1 as base.

        Field merging strategy:
        - Title: Prefer longer (more complete)
        - Abstract: Prefer longer (more detailed)
        - Authors: Union, deduplicated
        - Journal: Prefer non-empty, prefer PubMed version
        - Publication date: Prefer more specific (YYYY-MM-DD > YYYY-MM > YYYY)
        - MeSH terms: Union (PubMed typically has these)
        - Keywords: Union
        - URL: Union (keep both if different)
        - Citation count: Take maximum
        - Source: Keep paper1's source (preferred source)

        Args:
            paper1: Base paper (preferred source)
            paper2: Paper to merge into base

        Returns:
            Merged Paper object (new instance).
        """
        merged_dict = paper1.model_dump()

        # Title: prefer longer
        if len(paper2.title or "") > len(paper1.title or ""):
            merged_dict["title"] = paper2.title

        # Abstract: prefer longer (more detailed)
        if paper2.abstract and (
            not paper1.abstract or len(paper2.abstract) > len(paper1.abstract)
        ):
            merged_dict["abstract"] = paper2.abstract

        # Authors: union, deduplicated
        all_authors = set(paper1.authors or [])
        all_authors.update(paper2.authors or [])
        merged_dict["authors"] = list(sorted(all_authors))

        # Journal: prefer non-empty, PubMed preferred by source order
        if paper2.journal and not paper1.journal:
            merged_dict["journal"] = paper2.journal
        elif paper1.journal and paper2.journal:
            # Both have journal, prefer PubMed version
            if paper1.source == PaperSource.PUBMED:
                merged_dict["journal"] = paper1.journal
            elif paper2.source == PaperSource.PUBMED:
                merged_dict["journal"] = paper2.journal
            # Otherwise keep paper1's journal

        # Publication date: prefer more specific format
        if paper2.pub_date and paper1.pub_date:
            # More specific date has more separators
            specificity1 = paper1.pub_date.count("-") if paper1.pub_date else 0
            specificity2 = paper2.pub_date.count("-") if paper2.pub_date else 0
            if specificity2 > specificity1:
                merged_dict["pub_date"] = paper2.pub_date
        elif paper2.pub_date and not paper1.pub_date:
            merged_dict["pub_date"] = paper2.pub_date

        # MeSH terms: union
        all_mesh = set(paper1.mesh_terms or [])
        all_mesh.update(paper2.mesh_terms or [])
        merged_dict["mesh_terms"] = list(sorted(all_mesh))

        # Keywords: union
        all_keywords = set(paper1.keywords or [])
        all_keywords.update(paper2.keywords or [])
        merged_dict["keywords"] = list(sorted(all_keywords))

        # URL: keep both if different (comma-separated for now)
        if paper2.url and paper1.url and paper2.url != paper1.url:
            # Simple concatenation - could be improved
            merged_dict["url"] = f"{paper1.url},{paper2.url}"
        elif paper2.url and not paper1.url:
            merged_dict["url"] = paper2.url

        # Citation count: take maximum
        if paper2.citation_count is not None:
            if paper1.citation_count is None:
                merged_dict["citation_count"] = paper2.citation_count
            else:
                merged_dict["citation_count"] = max(
                    paper1.citation_count, paper2.citation_count
                )

        # Language: prefer paper1's
        if paper2.language and not paper1.language:
            merged_dict["language"] = paper2.language

        # DOI and PMID: if missing in paper1 but present in paper2, add
        if not paper1.doi and paper2.doi:
            merged_dict["doi"] = paper2.doi
        if not paper1.pmid and paper2.pmid:
            merged_dict["pmid"] = paper2.pmid

        # Crawled_at: use most recent
        if paper2.crawled_at and paper1.crawled_at:
            if paper2.crawled_at > paper1.crawled_at:
                merged_dict["crawled_at"] = paper2.crawled_at
        elif paper2.crawled_at and not paper1.crawled_at:
            merged_dict["crawled_at"] = paper2.crawled_at

        # Processing status: OR operation (if any paper has it processed)
        merged_dict["translated"] = paper1.translated or paper2.translated
        merged_dict["summarized"] = paper1.summarized or paper2.summarized

        # Create new Paper object with merged data
        # Keep paper1's source as primary source
        merged_dict["source"] = paper1.source

        return Paper(**merged_dict)

    def find_potential_duplicates(
        self, papers: List[Paper], similarity_threshold: float = 0.8
    ) -> List[Tuple[Paper, Paper, float]]:
        """Find potential duplicate pairs using fuzzy matching.

        Useful for papers without DOI/PMID that might be same publication
        with slightly different titles/authors.

        Args:
            papers: List of papers to check
            similarity_threshold: Minimum similarity score (0-1) to consider
                as potential duplicate

        Returns:
            List of tuples (paper1, paper2, similarity_score)
        """
        # TODO: Implement fuzzy matching using Levenshtein distance or
        # Jaccard similarity on title + authors
        # For now, return empty list
        return []


def deduplicate_papers(papers: List[Paper]) -> List[Paper]:
    """Convenience function for one-off deduplication.

    Args:
        papers: List of Paper objects

    Returns:
        Deduplicated list of Paper objects
    """
    deduplicator = Deduplicator()
    return deduplicator.deduplicate(papers)