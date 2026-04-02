"""Data models for SubSkin project.

This module contains Pydantic data models representing core entities:
- Paper: Scientific paper metadata
- Trial: Clinical trial information
- DataSource: Data source configuration
"""

from .paper import Paper, PaperSource, PaperUpdate, PaperSearchResult
from .trial import ClinicalTrial
from .data_source import DataSource

__all__ = [
    "Paper",
    "PaperSource",
    "PaperUpdate",
    "PaperSearchResult",
    "ClinicalTrial",
    "DataSource",
]
