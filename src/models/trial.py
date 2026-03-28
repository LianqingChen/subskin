"""Clinical trial data model for SubSkin project."""

from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, validator


class TrialPhase(str, Enum):
    """Clinical trial phases."""
    PHASE1 = "PHASE1"
    PHASE2 = "PHASE2"
    PHASE3 = "PHASE3"
    PHASE4 = "PHASE4"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    EARLY_PHASE1 = "EARLY_PHASE1"


class TrialStatus(str, Enum):
    """Clinical trial status."""
    RECRUITING = "RECRUITING"
    ACTIVE_NOT_RECRUITING = "ACTIVE_NOT_RECRUITING"
    COMPLETED = "COMPLETED"
    TERMINATED = "TERMINATED"
    SUSPENDED = "SUSPENDED"
    WITHDRAWN = "WITHDRAWN"
    UNKNOWN = "UNKNOWN"
    NOT_YET_RECRUITING = "NOT_YET_RECRUITING"
    ENROLLING_BY_INVITATION = "ENROLLING_BY_INVITATION"


class InterventionType(str, Enum):
    """Types of interventions in clinical trials."""
    DRUG = "DRUG"
    BIOLOGICAL = "BIOLOGICAL"
    DEVICE = "DEVICE"
    PROCEDURE = "PROCEDURE"
    BEHAVIORAL = "BEHAVIORAL"
    DIETARY_SUPPLEMENT = "DIETARY_SUPPLEMENT"
    RADIATION = "RADIATION"
    OTHER = "OTHER"


class Intervention(BaseModel):
    """Intervention in a clinical trial."""
    
    name: str = Field(..., description="Name of the intervention")
    type: InterventionType = Field(..., description="Type of intervention")
    description: Optional[str] = Field(None, description="Description of intervention")
    
    # For drug interventions
    drug_class: Optional[str] = Field(None, description="Drug class (e.g., JAK inhibitor)")
    dosage: Optional[str] = Field(None, description="Dosage information")
    route: Optional[str] = Field(None, description="Route of administration")


class Location(BaseModel):
    """Trial location."""
    
    facility: str = Field(..., description="Facility name")
    city: Optional[str] = Field(None, description="City")
    state: Optional[str] = Field(None, description="State/province")
    country: str = Field(..., description="Country")
    status: Optional[str] = Field(None, description="Recruitment status at this location")


class ClinicalTrial(BaseModel):
    """Represents a clinical trial for vitiligo."""
    
    # Core identifier
    nct_id: str = Field(
        ..., 
        description="ClinicalTrials.gov identifier (NCT number)",
        pattern=r'^NCT\d{8}$'
    )
    
    # Basic information
    title: str = Field(
        ..., 
        description="Title of the clinical trial",
        min_length=1,
        max_length=1000
    )
    condition: str = Field(
        ..., 
        description="Medical condition being studied"
    )
    
    # Interventions
    interventions: List[Intervention] = Field(
        default_factory=list,
        description="List of interventions"
    )
    
    # Trial details
    phase: TrialPhase = Field(
        ..., 
        description="Clinical trial phase"
    )
    status: TrialStatus = Field(
        ..., 
        description="Current status of the trial"
    )
    enrollment: Optional[int] = Field(
        None, 
        description="Number of participants (target or actual)",
        ge=0
    )
    
    # Sponsorship
    sponsor: str = Field(
        ..., 
        description="Sponsor of the trial"
    )
    collaborators: List[str] = Field(
        default_factory=list,
        description="Collaborating organizations"
    )
    
    # Dates
    start_date: Optional[str] = Field(
        None, 
        description="Trial start date (YYYY-MM format)"
    )
    completion_date: Optional[str] = Field(
        None, 
        description="Trial completion date (YYYY-MM format)"
    )
    last_update_date: Optional[str] = Field(
        None, 
        description="Last update date (YYYY-MM-DD format)"
    )
    
    # Locations
    locations: List[Location] = Field(
        default_factory=list,
        description="Trial locations"
    )
    
    # URLs and references
    url: str = Field(
        ..., 
        description="URL to the trial on ClinicalTrials.gov"
    )
    publication_urls: List[str] = Field(
        default_factory=list,
        description="URLs to related publications"
    )
    
    # Source and tracking
    crawled_at: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp when the trial was crawled"
    )
    last_verified: Optional[datetime] = Field(
        None, 
        description="Timestamp when the trial was last verified"
    )
    
    # Additional metadata
    study_type: Optional[str] = Field(
        None, 
        description="Type of study (e.g., INTERVENTIONAL, OBSERVATIONAL)"
    )
    primary_outcome: Optional[str] = Field(
        None, 
        description="Primary outcome measure"
    )
    secondary_outcome: Optional[str] = Field(
        None, 
        description="Secondary outcome measure"
    )
    inclusion_criteria: Optional[str] = Field(
        None, 
        description="Inclusion criteria"
    )
    exclusion_criteria: Optional[str] = Field(
        None, 
        description="Exclusion criteria"
    )
    
    @validator('url')
    def validate_url(cls, v):
        """Validate URL points to ClinicalTrials.gov."""
        if not v.startswith('https://clinicaltrials.gov/ct2/show/'):
            # Ensure it's the correct format
            nct_match = v.split('/')[-1] if '/' in v else v
            if nct_match.startswith('NCT'):
                return f'https://clinicaltrials.gov/ct2/show/{nct_match}'
        return v
    
    @validator('start_date', 'completion_date', 'last_update_date')
    def validate_date_format(cls, v):
        """Validate date formats."""
        if v is None:
            return v
        
        # ClinicalTrials.gov uses YYYY-MM for start/completion dates
        # and YYYY-MM-DD for last update dates
        
        # Check YYYY-MM format
        if len(v) == 7 and v[4] == '-':
            try:
                year, month = v.split('-')
                int(year), int(month)
                if 1 <= int(month) <= 12:
                    return v
            except (ValueError, IndexError):
                pass
        
        # Check YYYY-MM-DD format
        if len(v) == 10 and v[4] == '-' and v[7] == '-':
            try:
                year, month, day = v.split('-')
                int(year), int(month), int(day)
                return v
            except (ValueError, IndexError):
                pass
        
        # Try to extract year-month
        import re
        ym_match = re.search(r'(\d{4})-(\d{2})', v)
        if ym_match:
            return f"{ym_match.group(1)}-{ym_match.group(2)}"
        
        # Try to extract just year
        year_match = re.search(r'\b(19|20)\d{2}\b', v)
        if year_match:
            return year_match.group(0)
        
        return v
    
    def is_jak_inhibitor_trial(self) -> bool:
        """Check if this trial involves JAK inhibitors."""
        jak_keywords = ['jak', 'janus kinase', 'ruxolitinib', 'tofacitinib', 
                       'upadacitinib', 'ritlecitinib', 'povorcitinib']
        
        for intervention in self.interventions:
            intervention_lower = intervention.name.lower()
            if any(keyword in intervention_lower for keyword in jak_keywords):
                return True
            
            if intervention.drug_class and 'jak' in intervention.drug_class.lower():
                return True
        
        # Also check title and condition
        search_text = f"{self.title} {self.condition}".lower()
        if any(keyword in search_text for keyword in jak_keywords):
            return True
        
        return False
    
    def is_active(self) -> bool:
        """Check if trial is currently active."""
        active_statuses = [
            TrialStatus.RECRUITING,
            TrialStatus.ACTIVE_NOT_RECRUITING,
            TrialStatus.ENROLLING_BY_INVITATION,
            TrialStatus.NOT_YET_RECRUITING
        ]
        return self.status in active_statuses
    
    def is_completed(self) -> bool:
        """Check if trial is completed."""
        return self.status == TrialStatus.COMPLETED
    
    def get_countries(self) -> List[str]:
        """Get list of countries where trial is conducted."""
        countries = set()
        for location in self.locations:
            if location.country:
                countries.add(location.country)
        return list(countries)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert trial to dictionary."""
        return self.dict()
    
    def get_intervention_types(self) -> List[str]:
        """Get list of intervention types."""
        types = set()
        for intervention in self.interventions:
            types.add(intervention.type.value)
        return list(types)


class TrialUpdate(BaseModel):
    """Model for updating trial data (partial updates)."""
    
    status: Optional[TrialStatus] = None
    enrollment: Optional[int] = None
    completion_date: Optional[str] = None
    last_update_date: Optional[str] = None
    last_verified: Optional[datetime] = None
    publication_urls: Optional[List[str]] = None
    
    class Config:
        extra = "forbid"


class TrialSearchResult(BaseModel):
    """Result of clinical trial search."""
    
    trial: ClinicalTrial
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