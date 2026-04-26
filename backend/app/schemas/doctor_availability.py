from typing import Optional
from datetime import date
from pydantic import BaseModel

class DoctorScheduleBase(BaseModel):
    day_of_week: int
    start_time: str
    end_time: str
    is_active: Optional[bool] = True

class DoctorScheduleCreate(DoctorScheduleBase):
    doctor_id: int

class DoctorSchedule(DoctorScheduleBase):
    id: int
    doctor_id: int

    class Config:
        from_attributes = True

class DoctorLeaveBase(BaseModel):
    date: date
    reason: Optional[str] = None

class DoctorLeaveCreate(DoctorLeaveBase):
    doctor_id: int

class DoctorLeave(DoctorLeaveBase):
    id: int
    doctor_id: int

    class Config:
        from_attributes = True