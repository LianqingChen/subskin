"""Data source models for the SubSkin project.

This module defines Pydantic models for representing and validating data sources
based on the comprehensive vitiligo data sources research report.
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator


class DataSourceCategory(str, Enum):
    """Categories of data sources."""
    ENGLISH_RESEARCH = "english_research"
    CHINESE_RESEARCH = "chinese_research"
    PATIENT_COMMUNITY = "patient_community"
    CLINICAL_TRIALS = "clinical_trials"
    GUIDELINES = "guidelines"
    IMAGE_DATA = "image_data"


class DataSourceType(str, Enum):
    """Types of data sources."""
    COMPREHENSIVE_BIOMEDICAL_LITERATURE = "comprehensive_biomedical_literature"
    GENETIC_VARIANT_DATABASE = "genetic_variant_database"
    GENE_PROTEIN_DATABASE = "gene_protein_database"
    PREPRINT_SERVER = "preprint_server"
    COMPREHENSIVE_ACADEMIC_LITERATURE = "comprehensive_academic_literature"
    BIOMEDICAL_LITERATURE = "biomedical_literature"
    MEDICAL_JOURNAL = "medical_journal"
    PATIENT_FORUM = "patient_forum"
    DOCTOR_PATIENT_PLATFORM = "doctor_patient_platform"
    MEDICAL_ENCYCLOPEDIA = "medical_encyclopedia"
    CLINICAL_TRIAL_REGISTRY = "clinical_trial_registry"
    DRUG_REGULATORY_AGENCY = "drug_regulatory_agency"
    DRUG_PIPELINE_TRACKING = "drug_pipeline_tracking"
    CLINICAL_GUIDELINE = "clinical_guideline"
    SKIN_IMAGE_DATABASE = "skin_image_database"
    OPEN_SOURCE_CODE_DATASET = "open_source_code_dataset"


class AccessMethod(str, Enum):
    """Methods for accessing data sources."""
    API = "api"
    WEB_BROWSING = "web_browsing"
    WEB_SCRAPING = "web_scraping"
    DIRECT_DOWNLOAD = "direct_download"
    WEB_DOWNLOAD = "web_download"
    GIT_CLONE = "git_clone"


class CostModel(str, Enum):
    """Cost models for data sources."""
    FREE = "free"
    PAID_SUBSCRIPTION = "paid_subscription"
    FREEMIUM = "freemium"
    INSTITUTIONAL_ACCESS = "institutional_access"


class PriorityLevel(str, Enum):
    """Priority levels for data source collection."""
    PRIORITY_1 = "priority_1"
    PRIORITY_2 = "priority_2"
    PRIORITY_3 = "priority_3"


class CollectionMethod(str, Enum):
    """Methods for collecting data from sources."""
    API_CRAWLING = "api_crawling"
    WEB_SCRAPING = "web_scraping"
    DIRECT_DOWNLOAD = "direct_download"
    WEB_DOWNLOAD = "web_download"
    GIT_CLONE = "git_clone"


class DataSource(BaseModel):
    """Represents a data source for vitiligo information."""
    
    # Core identification
    id: str = Field(..., description="Unique identifier for the data source")
    name: str = Field(..., description="Human-readable name of the data source")
    category: DataSourceCategory = Field(..., description="Category of the data source")
    
    # Access information
    url: str = Field(..., description="URL of the data source")
    type: DataSourceType = Field(..., description="Type of data source")
    language: str = Field(..., description="Primary language of the data source")
    access_method: AccessMethod = Field(..., description="Method for accessing the data")
    cost: CostModel = Field(..., description="Cost model for accessing the data")
    
    # Quality and priority
    data_quality: int = Field(
        ge=1, le=5, 
        description="Data quality rating on a 1-5 scale (5=highest quality)"
    )
    priority: PriorityLevel = Field(..., description="Collection priority level")
    collection_method: CollectionMethod = Field(
        ..., 
        description="Recommended method for collecting data"
    )
    
    # Optional fields
    api_endpoint: Optional[str] = Field(
        None, 
        description="API endpoint URL if applicable"
    )
    rate_limit: Optional[int] = Field(
        None, 
        description="Rate limit in requests per second"
    )
    search_terms: List[str] = Field(
        default_factory=list, 
        description="Recommended search terms for this data source"
    )
    estimated_volume: Optional[int] = Field(
        None, 
        description="Estimated volume of data available"
    )
    file_format: Optional[str] = Field(
        None, 
        description="File format if applicable (e.g., 'pdf', 'csv')"
    )
    ethical_considerations: Optional[List[str]] = Field(
        None, 
        description="Ethical considerations for data collection"
    )
    notes: Optional[str] = Field(
        None, 
        description="Additional notes about the data source"
    )
    
    # Metadata
    last_verified: Optional[str] = Field(
        None, 
        description="Date when this data source was last verified"
    )
    is_active: bool = Field(
        True, 
        description="Whether this data source is currently active"
    )
    
    @validator("url")
    def validate_url(cls, v):
        """Validate URL format."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v
    
    @validator("data_quality")
    def validate_data_quality(cls, v):
        """Ensure data quality is within valid range."""
        if not 1 <= v <= 5:
            raise ValueError("Data quality must be between 1 and 5")
        return v
    
    def get_collection_tools(self) -> List[str]:
        """Get recommended tools for collecting data from this source."""
        tools_map = {
            CollectionMethod.API_CRAWLING: ["requests", "aiohttp", "Biopython"],
            CollectionMethod.WEB_SCRAPING: ["scrapy", "selenium", "beautifulsoup4"],
            CollectionMethod.DIRECT_DOWNLOAD: ["requests", "wget"],
            CollectionMethod.WEB_DOWNLOAD: ["requests", "selenium"],
            CollectionMethod.GIT_CLONE: ["git"],
        }
        return tools_map.get(self.collection_method, [])
    
    def should_use_rate_limiting(self) -> bool:
        """Check if rate limiting should be used for this data source."""
        return self.collection_method in [
            CollectionMethod.API_CRAWLING, 
            CollectionMethod.WEB_SCRAPING
        ]
    
    def requires_ethical_considerations(self) -> bool:
        """Check if this data source requires ethical considerations."""
        return self.type in [
            DataSourceType.PATIENT_FORUM,
            DataSourceType.DOCTOR_PATIENT_PLATFORM,
        ]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert data source to dictionary."""
        return self.dict()


class DataSourceCategoryInfo(BaseModel):
    """Information about a data source category."""
    
    id: str = Field(..., description="Category identifier")
    name: str = Field(..., description="Category name")
    description: str = Field(..., description="Category description")
    color: str = Field(..., description="Color code for visualization")
    
    @validator("color")
    def validate_color(cls, v):
        """Validate color format."""
        if not v.startswith("#") or len(v) != 7:
            raise ValueError("Color must be in hex format, e.g., #1e88e5")
        return v


class PriorityGroup(BaseModel):
    """Group of data sources with the same priority level."""
    
    name: str = Field(..., description="Priority group name")
    description: str = Field(..., description="Priority group description")
    data_sources: List[str] = Field(
        ..., 
        description="List of data source IDs in this priority group"
    )


class CollectionStrategy(BaseModel):
    """Strategy for collecting data from sources."""
    
    id: str = Field(..., description="Strategy identifier")
    description: str = Field(..., description="Strategy description")
    recommended_tools: List[str] = Field(
        ..., 
        description="Recommended tools for this strategy"
    )
    rate_limiting: bool = Field(
        default=True, 
        description="Whether rate limiting is recommended"
    )
    caching: bool = Field(
        default=True, 
        description="Whether caching is recommended"
    )
    ethical_guidelines: Optional[List[str]] = Field(
        None, 
        description="Ethical guidelines for this collection strategy"
    )


class QualityStandard(BaseModel):
    """Quality standards for data collection and processing."""
    
    source_credibility: List[str] = Field(
        ..., 
        description="Standards for assessing source credibility"
    )
    content_validation: List[str] = Field(
        ..., 
        description="Standards for content validation"
    )
    data_cleaning: List[str] = Field(
        ..., 
        description="Standards for data cleaning"
    )
    privacy_protection: List[str] = Field(
        ..., 
        description="Standards for privacy protection"
    )