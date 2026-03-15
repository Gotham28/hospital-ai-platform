from typing import Optional
from datetime import datetime
from pydantic import BaseModel

class HospitalBase(BaseModel):
    name: str
    slug: str
    address: Optional[str] = None
    is_active: Optional[bool] = True
    # ADD THESE:
    system_prompt: Optional[str] = "You are Arogya, a helpful assistant..."
    google_sheet_id: Optional[str] = None

class HospitalCreate(HospitalBase):
    pass

class HospitalUpdate(HospitalBase):
    name: Optional[str] = None
    slug: Optional[str] = None

class Hospital(HospitalBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True