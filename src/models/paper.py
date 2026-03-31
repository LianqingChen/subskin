"""Paper data model for SubSkin project."""

from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, field_validator, ConfigDict


class PaperSource(str, Enum):
    """Source of the paper data."""
    PUBMED = "pubmed"
    SEMANTIC_SCHOLAR = "semantic_scholar"
    CNKI = "cnki"
    SINOMED = "sinomed"
    OTHER = "other"


class Paper(BaseModel):
    """Represents a scientific paper about vitiligo."""
    
    # Core identifiers
    pmid: Optional[str] = Field(
        None, 
        description="PubMed ID"
    )
    doi: Optional[str] = Field(
        None, 
        description="Digital Object Identifier"
    )
    
    # Basic metadata
    title: str = Field(
        ..., 
        description="Title of the paper",
        min_length=1,
        max_length=1000
    )
    abstract: Optional[str] = Field(
        None, 
        description="Abstract of the paper"
    )
    
    # Authors and publication info
    authors: List[str] = Field(
        default_factory=list,
        description="List of authors"
    )
    journal: Optional[str] = Field(
        None, 
        description="Journal name"
    )
    pub_date: Optional[str] = Field(
        None, 
        description="Publication date (YYYY-MM-DD format)"
    )
    
    # Medical metadata
    mesh_terms: List[str] = Field(
        default_factory=list,
        description="Medical Subject Headings (MeSH) terms"
    )
    keywords: List[str] = Field(
        default_factory=list,
        description="Keywords from the paper"
    )
    
    # Source and tracking
    source: PaperSource = Field(
        ..., 
        description="Source of the paper data"
    )
    crawled_at: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp when the paper was crawled"
    )
    
    # Additional metadata
    url: Optional[str] = Field(
        None, 
        description="URL to the paper"
    )
    citation_count: Optional[int] = Field(
        None, 
        description="Number of citations"
    )
    language: str = Field(
        "en", 
        description="Language of the paper"
    )
    
    # Translation and summarization results
    chinese_abstract: Optional[str] = Field(
        None,
        description="Chinese translation of the abstract"
    )
    summary: Optional[str] = Field(
        None,
        description="Patient-friendly Chinese summary"
    )
    
    # Processing status
    translated: bool = Field(
        False, 
        description="Whether abstract has been translated to Chinese"
    )
    summarized: bool = Field(
        False, 
        description="Whether paper has been summarized"
    )
    
    @field_validator('pub_date')
    @classmethod
    def validate_pub_date(cls, v):
        """Validate publication date format."""
        if v is None:
            return v
        
        # Try to parse date
        try:
            # Simple validation for YYYY-MM-DD format
            if len(v) == 10 and v[4] == '-' and v[7] == '-':
                year, month, day = v.split('-')
                int(year), int(month), int(day)
                return v
        except (ValueError, IndexError):
            pass
        
        # Try to extract year from other formats
        try:
            # Try to get just the year
            import re
            year_match = re.search(r'\b(19|20)\d{2}\b', v)
            if year_match:
                return year_match.group(0)
        except:
            pass
        
        # If can't parse, return as-is with warning
        return v
    
    @field_validator('doi')
    @classmethod
    def validate_doi(cls, v):
        """Validate DOI format."""
        if v is None:
            return v
        
        # Basic DOI validation (should start with 10.)
        if not v.startswith('10.'):
            # Try to extract DOI from URL
            import re
            doi_match = re.search(r'10\.[^/]+/.+', v)
            if doi_match:
                return doi_match.group(0)
        
        return v
    
    @field_validator('url')
    @classmethod
    def validate_url(cls, v):
        """Validate URL format."""
        if v is None:
            return v
        
        if not v.startswith(('http://', 'https://')):
            # Try to add https:// if missing
            return f'https://{v}'
        
        return v
    
    def get_citation(self) -> str:
        """Generate a citation string."""
        authors_str = ', '.join(self.authors[:3])
        if len(self.authors) > 3:
            authors_str += ' et al.'
        
        year = ''
        if self.pub_date:
            # Extract year from pub_date
            year_match = self.pub_date[:4] if len(self.pub_date) >= 4 else ''
            if year_match.isdigit():
                year = f' ({year_match})'
        
        journal_part = f'. {self.journal}' if self.journal else ''
        
        return f'{authors_str}{year}. {self.title}{journal_part}.'
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert paper to dictionary."""
        return self.model_dump()
    
    def get_identifiers(self) -> Dict[str, str]:
        """Get all identifiers for the paper."""
        identifiers = {}
        if self.pmid:
            identifiers['pmid'] = self.pmid
        if self.doi:
            identifiers['doi'] = self.doi
        if self.url:
            identifiers['url'] = self.url
        
        return identifiers
    
    def is_complete(self) -> bool:
        """Check if paper has minimal required data."""
        return bool(self.title and (self.pmid or self.doi or self.url))


class PaperUpdate(BaseModel):
    """Model for updating paper data (partial updates)."""
    
    title: Optional[str] = None
    abstract: Optional[str] = None
    authors: Optional[List[str]] = None
    journal: Optional[str] = None
    pub_date: Optional[str] = None
    mesh_terms: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    citation_count: Optional[int] = None
    chinese_abstract: Optional[str] = None
    summary: Optional[str] = None
    translated: Optional[bool] = None
    summarized: Optional[bool] = None
    
    model_config = ConfigDict(extra="forbid")  # Don't allow extra fields


class PaperSearchResult(BaseModel):
    """Result of paper search."""
    
    paper: Paper
    relevance_score: float = Field(
        ..., 
        ge=0.0, 
        le=1.0,
        description="Relevance score (0-1)"
    )
    match_terms: List[str] = Field(
        default_factory=list,
        description="Terms that matched in the search"
    )