from typing import Optional
from datetime import datetime
from pydantic import BaseModel

# Shared properties
class HospitalBase(BaseModel):
    name: str
    slug: str
    address: Optional[str] = None
    is_active: Optional[bool] = True

# Properties to receive on creation
class HospitalCreate(HospitalBase):
    pass

# Properties to receive on update
class HospitalUpdate(HospitalBase):
    pass

# Properties to return to client
class Hospital(HospitalBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True