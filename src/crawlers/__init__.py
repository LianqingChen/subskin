"""Crawlers module for SubSkin project.

This module contains web crawlers for various scientific sources:
- pubmed_crawler: PubMed paper crawler
- semantic_scholar_crawler: Semantic Scholar paper crawler
- clinical_trials_crawler: ClinicalTrials.gov clinical trial crawler
- cma_crawler: Chinese Medical Association (中华医学会) article crawler
"""

from .pubmed_crawler import PubMedCrawler
from .semantic_scholar_crawler import SemanticScholarCrawler
from .clinical_trials_crawler import ClinicalTrialsCrawler
from .cma_crawler import CMACrawler

__all__ = [
    "PubMedCrawler",
    "SemanticScholarCrawler",
    "ClinicalTrialsCrawler",
    "CMACrawler",
]
