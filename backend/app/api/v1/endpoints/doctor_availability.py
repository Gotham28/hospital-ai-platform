from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.api.deps import get_db, get_current_tenant
from app.models.doctor import Doctor
from app.models.doctor_availability import DoctorSchedule, DoctorLeave
from app.schemas.doctor_availability import (
    DoctorSchedule as DoctorScheduleSchema, 
    DoctorScheduleCreate, 
    DoctorLeave as DoctorLeaveSchema, 
    DoctorLeaveCreate
)

router = APIRouter()

# ==========================================
# SCHEDULES
# ==========================================

@router.post("/schedules/", response_model=DoctorScheduleSchema)
def create_schedule(
    payload: DoctorScheduleCreate,
    db: Session = Depends(get_db),
    _tenant: int = Depends(get_current_tenant)
):
    # Security: Verify doctor belongs to the admin's hospital
    doctor = db.query(Doctor).filter(Doctor.id == payload.doctor_id, Doctor.hospital_id == _tenant).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found in this hospital")

    db_item = DoctorSchedule(**payload.model_dump())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

@router.get("/schedules/doctor/{doctor_id}", response_model=List[DoctorScheduleSchema])
def get_doctor_schedules(
    doctor_id: int,
    db: Session = Depends(get_db),
    _tenant: int = Depends(get_current_tenant)
):
    # Security check included
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id, Doctor.hospital_id == _tenant).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    
    return db.query(DoctorSchedule).filter(DoctorSchedule.doctor_id == doctor_id).all()

@router.delete("/schedules/{schedule_id}")
def delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    _tenant: int = Depends(get_current_tenant)
):
    # Join with Doctor table to ensure cross-tenant security
    schedule = db.query(DoctorSchedule).join(Doctor).filter(
        DoctorSchedule.id == schedule_id, 
        Doctor.hospital_id == _tenant
    ).first()
    
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
        
    db.delete(schedule)
    db.commit()
    return {"status": "success"}


# ==========================================
# LEAVES
# ==========================================

@router.post("/leaves/", response_model=DoctorLeaveSchema)
def create_leave(
    payload: DoctorLeaveCreate,
    db: Session = Depends(get_db),
    _tenant: int = Depends(get_current_tenant)
):
    doctor = db.query(Doctor).filter(Doctor.id == payload.doctor_id, Doctor.hospital_id == _tenant).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found in this hospital")

    db_item = DoctorLeave(**payload.model_dump())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

@router.get("/leaves/doctor/{doctor_id}", response_model=List[DoctorLeaveSchema])
def get_doctor_leaves(
    doctor_id: int,
    db: Session = Depends(get_db),
    _tenant: int = Depends(get_current_tenant)
):
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id, Doctor.hospital_id == _tenant).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
        
    return db.query(DoctorLeave).filter(DoctorLeave.doctor_id == doctor_id).order_by(DoctorLeave.date).all()

@router.delete("/leaves/{leave_id}")
def delete_leave(
    leave_id: int,
    db: Session = Depends(get_db),
    _tenant: int = Depends(get_current_tenant)
):
    leave = db.query(DoctorLeave).join(Doctor).filter(
        DoctorLeave.id == leave_id, 
        Doctor.hospital_id == _tenant
    ).first()
    
    if not leave:
        raise HTTPException(status_code=404, detail="Leave not found")
        
    db.delete(leave)
    db.commit()
    return {"status": "success"}