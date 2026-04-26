from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.api.deps import get_db, get_token_payload
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
    token_data: dict = Depends(get_token_payload)
):
    doctor = db.query(Doctor).filter(Doctor.id == payload.doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
        
    if token_data.get("role") != "superadmin" and str(token_data.get("hospital_id")) != str(doctor.hospital_id):
        raise HTTPException(status_code=403, detail="Access denied")

    db_item = DoctorSchedule(**payload.model_dump())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

@router.get("/schedules/doctor/{doctor_id}", response_model=List[DoctorScheduleSchema])
def get_doctor_schedules(
    doctor_id: int,
    db: Session = Depends(get_db),
    token_data: dict = Depends(get_token_payload)
):
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    
    if token_data.get("role") != "superadmin" and str(token_data.get("hospital_id")) != str(doctor.hospital_id):
        raise HTTPException(status_code=403, detail="Access denied")
    
    return db.query(DoctorSchedule).filter(DoctorSchedule.doctor_id == doctor_id).all()

@router.delete("/schedules/{schedule_id}")
def delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    token_data: dict = Depends(get_token_payload)
):
    schedule = db.query(DoctorSchedule).filter(DoctorSchedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
        
    doctor = db.query(Doctor).filter(Doctor.id == schedule.doctor_id).first()
    if token_data.get("role") != "superadmin" and doctor and str(token_data.get("hospital_id")) != str(doctor.hospital_id):
        raise HTTPException(status_code=403, detail="Access denied")
        
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
    token_data: dict = Depends(get_token_payload)
):
    doctor = db.query(Doctor).filter(Doctor.id == payload.doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    if token_data.get("role") != "superadmin" and str(token_data.get("hospital_id")) != str(doctor.hospital_id):
        raise HTTPException(status_code=403, detail="Access denied")

    db_item = DoctorLeave(**payload.model_dump())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

@router.get("/leaves/doctor/{doctor_id}", response_model=List[DoctorLeaveSchema])
def get_doctor_leaves(
    doctor_id: int,
    db: Session = Depends(get_db),
    token_data: dict = Depends(get_token_payload)
):
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
        
    if token_data.get("role") != "superadmin" and str(token_data.get("hospital_id")) != str(doctor.hospital_id):
        raise HTTPException(status_code=403, detail="Access denied")
        
    return db.query(DoctorLeave).filter(DoctorLeave.doctor_id == doctor_id).order_by(DoctorLeave.date).all()

@router.delete("/leaves/{leave_id}")
def delete_leave(
    leave_id: int,
    db: Session = Depends(get_db),
    token_data: dict = Depends(get_token_payload)
):
    leave = db.query(DoctorLeave).filter(DoctorLeave.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Leave not found")
        
    doctor = db.query(Doctor).filter(Doctor.id == leave.doctor_id).first()
    if token_data.get("role") != "superadmin" and doctor and str(token_data.get("hospital_id")) != str(doctor.hospital_id):
        raise HTTPException(status_code=403, detail="Access denied")
        
    db.delete(leave)
    db.commit()
    return {"status": "success"}