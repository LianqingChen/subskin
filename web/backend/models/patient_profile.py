from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class PatientProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    relationship: str
    gender: Optional[str] = None
    birth_date: Optional[date] = None
    diagnosis_date: Optional[date] = None
    vitiligo_type: Optional[str] = None
    notes: Optional[str] = None


class PatientProfileUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    relationship: Optional[str] = None
    gender: Optional[str] = None
    birth_date: Optional[date] = None
    diagnosis_date: Optional[date] = None
    vitiligo_type: Optional[str] = None
    notes: Optional[str] = None


class PatientProfileResponse(BaseModel):
    id: int
    name: str
    relationship: str
    gender: Optional[str] = None
    birth_date: Optional[date] = None
    diagnosis_date: Optional[date] = None
    vitiligo_type: Optional[str] = None
    notes: Optional[str] = None
    is_self: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ModuleDefaults(BaseModel):
    tracker_profile_id: Optional[int] = None
    report_profile_id: Optional[int] = None
    diary_profile_id: Optional[int] = None
