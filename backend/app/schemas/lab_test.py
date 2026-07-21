from typing import Optional
from pydantic import BaseModel

class LabTestBase(BaseModel):
    name: str
    category: Optional[str] = None
    price: Optional[float] = None
    prerequisites: Optional[str] = None
    turnaround_time: Optional[str] = None
    is_inhouse: Optional[bool] = True
    # Feature 3: outsourced lab test flag
    is_outsourced: Optional[bool] = False
    outsourced_note: Optional[str] = None  # TODO: empty pending clinic wording sign-off

class LabTestCreate(LabTestBase):
    hospital_id: int

class LabTestUpdate(LabTestBase):
    name: Optional[str] = None

class LabTest(LabTestBase):
    id: int
    hospital_id: int

    class Config:
        from_attributes = True