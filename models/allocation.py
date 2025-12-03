"""
Allocation request data models
"""
#allocation.py

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, Dict, Any
from datetime import datetime, date


class AllocationRequest(BaseModel):
    """Allocation request form model"""
    emp_code: str = Field(..., description="Employee code")
    emp_name: str = Field(..., description="Employee name")
    client_name: str = Field(..., description="Client name")
    project_name: str = Field(..., description="Project name")
    project_id: str = Field(..., description="Project ID")
    sow_cr_id: str = Field(..., description="SOW/CR ID")
    role: str = Field(..., description="Role")
    rate: float = Field(..., description="Rate")
    allocation_category: str = Field(..., description="Allocation category")
    allocation_percentage: float = Field(..., ge=0, le=100, description="Allocation percentage")
    start_date: date = Field(..., description="Start date")
    end_date: date = Field(..., description="End date")
    rr_id: str = Field(..., description="RR ID")
    candidate_id: int = Field(..., description="Candidate ID")
    requirement_text: str = Field(..., description="Original requirement text")
    match_score: float = Field(..., ge=0, le=100, description="Match score percentage")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON storage"""
        return {
            "emp_code": self.emp_code,
            "emp_name": self.emp_name,
            "client_name": self.client_name,
            "project_name": self.project_name,
            "project_id": self.project_id,
            "sow_cr_id": self.sow_cr_id,
            "role": self.role,
            "rate": self.rate,
            "allocation_category": self.allocation_category,
            "allocation_percentage": self.allocation_percentage,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "rr_id": self.rr_id,
        }


class AllocationRecord(BaseModel):
    """Allocation record stored in database"""
    id: Optional[int] = None
    candidate_id: int
    requirement_text: str
    match_score: float
    user_details: Dict[str, Any]
    status: str = "pending"  # pending, approved, rejected
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


