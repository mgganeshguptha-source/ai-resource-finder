"""
Candidate data models
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Dict, List, Optional, Any
from datetime import datetime


class CandidateProfile(BaseModel):
    """Candidate profile model"""
    id: Optional[int] = None
    name: str
    email: EmailStr
    raw_text: Optional[str] = None
    extracted_skills: Dict[str, Any] = Field(default_factory=dict)
    years_of_experience: Dict[str, float] = Field(default_factory=dict)
    domain_tags: List[str] = Field(default_factory=list)
    experience_summary: Optional[str] = None  # Compact summary of key projects and experience
    embedding: Optional[List[float]] = None
    cv_s3_key: Optional[str] = None
    cv_s3_url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "John Doe",
                "email": "john.doe@example.com",
                "raw_text": "Full CV text...",
                "extracted_skills": {
                    "Python": {"proficiency": "expert", "evidence": "5 years of Python development"},
                    "AWS": {"proficiency": "intermediate", "evidence": "2 years of AWS cloud experience"}
                },
                "years_of_experience": {
                    "Python": 5.0,
                    "AWS": 2.0
                },
                "domain_tags": ["Cloud Computing", "Backend Development"]
            }
        }


class SkillExtraction(BaseModel):
    """Extracted skill information"""
    skill_name: str
    proficiency: str  # beginner, intermediate, advanced, expert
    years: Optional[float] = None
    evidence: str
    domain: Optional[str] = None


