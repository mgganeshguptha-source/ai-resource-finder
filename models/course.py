"""
Training course data models
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class TrainingCourse(BaseModel):
    """Training course model"""
    id: Optional[int] = None
    title: str
    description: str
    level: Optional[str] = None  # beginner, intermediate, advanced
    prerequisites: List[str] = Field(default_factory=list)
    url: Optional[str] = None  # Course URL/link
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "Advanced Python Programming",
                "description": "Learn advanced Python concepts including decorators, generators, and async programming",
                "level": "advanced",
                "prerequisites": ["Python basics", "Object-oriented programming"],
                "metadata": {
                    "duration": "40 hours",
                    "format": "online",
                    "certification": True
                }
            }
        }


class CourseRecommendation(BaseModel):
    """Course recommendation with rationale"""
    course: TrainingCourse
    score: float  # 0-1
    rationale: str
    gaps_addressed: List[str]  # List of skill gaps this course addresses


