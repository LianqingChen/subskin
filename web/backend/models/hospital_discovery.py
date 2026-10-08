"""Public, aggregate-only hospital experience discovery models."""
from typing import List, Optional

from pydantic import BaseModel, Field


class ExperienceDimensionSummary(BaseModel):
    dimension: str
    answered: int
    satisfied: int
    neutral: int
    unsatisfied: int
    na: int
    eligible: bool
    reference_score: Optional[float] = None


class HospitalExperienceSummary(BaseModel):
    hospital_id: int
    participants: int
    dimensions: List[ExperienceDimensionSummary] = Field(default_factory=list)


class HospitalExperienceResponse(BaseModel):
    window_start: str
    as_of: str
    minimum: int = 20
    window_days: int = 365
    method: str = "wilson-lower-95-v1"
    items: List[HospitalExperienceSummary] = Field(default_factory=list)
