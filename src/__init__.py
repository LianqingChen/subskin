"""SubSkin - Vitiligo knowledge base project with AI-powered medical paper summarization.

This project automatically collects vitiligo-related papers from PubMed,
Semantic Scholar, and ClinicalTrials.gov, uses LLMs to translate and summarize
medical papers into patient-friendly Chinese content, and tracks drug development
progress for JAK inhibitors and other treatments.
"""

__version__ = "0.1.0"

from src.config import Settings, settings
from src.exceptions import CrawlerError, APIError, RateLimitError, CacheError

__all__ = [
    "__version__",
    "Settings",
    "settings",
    "CrawlerError",
    "APIError",
    "RateLimitError",
    "CacheError",
]
