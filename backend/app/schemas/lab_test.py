from typing import Optional
from pydantic import BaseModel

class LabTestBase(BaseModel):
    name: str
    category: Optional[str] = None
    price: Optional[float] = None
    prerequisites: Optional[str] = None
    turnaround_time: Optional[str] = None
    is_inhouse: Optional[bool] = True

class LabTestCreate(LabTestBase):
    hospital_id: int

class LabTestUpdate(LabTestBase):
    name: Optional[str] = None

class LabTest(LabTestBase):
    id: int
    hospital_id: int

    class Config:
        from_attributes = True