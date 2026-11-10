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
    DoctorLeaveCreate,
)

router = APIRouter()


def _authorized_hospital_id(hospital_id: int, token_data: dict) -> int:
    """Validate the requested tenant before using it in a scoped ORM query."""
    if token_data.get("role") == "superadmin":
        return hospital_id

    user_hospital_id = token_data.get("hospital_id")
    if user_hospital_id is None or str(user_hospital_id) != str(hospital_id):
        raise HTTPException(status_code=403, detail="Access denied")
    return int(user_hospital_id)


# ==========================================
# SCHEDULES
# ==========================================

@router.post("/schedules/", response_model=DoctorScheduleSchema)
def create_schedule(
    payload: DoctorScheduleCreate,
    hospital_id: int,
    db: Session = Depends(get_db),
    token_data: dict = Depends(get_token_payload),
):
    hospital_id = _authorized_hospital_id(hospital_id, token_data)
    doctor = db.query(Doctor).filter(
        Doctor.id == payload.doctor_id,
        Doctor.hospital_id == hospital_id,
    ).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    db_item = DoctorSchedule(**payload.model_dump())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


@router.get("/schedules/doctor/{doctor_id}", response_model=List[DoctorScheduleSchema])
def get_doctor_schedules(
    doctor_id: int,
    hospital_id: int,
    db: Session = Depends(get_db),
    token_data: dict = Depends(get_token_payload),
):
    hospital_id = _authorized_hospital_id(hospital_id, token_data)
    doctor = db.query(Doctor).filter(
        Doctor.id == doctor_id,
        Doctor.hospital_id == hospital_id,
    ).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    return (
        db.query(DoctorSchedule)
        .join(Doctor, Doctor.id == DoctorSchedule.doctor_id)
        .filter(DoctorSchedule.doctor_id == doctor_id, Doctor.hospital_id == hospital_id)
        .all()
    )


@router.delete("/schedules/{schedule_id}")
def delete_schedule(
    schedule_id: int,
    hospital_id: int,
    db: Session = Depends(get_db),
    token_data: dict = Depends(get_token_payload),
):
    hospital_id = _authorized_hospital_id(hospital_id, token_data)
    schedule = (
        db.query(DoctorSchedule)
        .join(Doctor, Doctor.id == DoctorSchedule.doctor_id)
        .filter(DoctorSchedule.id == schedule_id, Doctor.hospital_id == hospital_id)
        .first()
    )
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
    hospital_id: int,
    db: Session = Depends(get_db),
    token_data: dict = Depends(get_token_payload),
):
    hospital_id = _authorized_hospital_id(hospital_id, token_data)
    doctor = db.query(Doctor).filter(
        Doctor.id == payload.doctor_id,
        Doctor.hospital_id == hospital_id,
    ).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    db_item = DoctorLeave(**payload.model_dump())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


@router.get("/leaves/doctor/{doctor_id}", response_model=List[DoctorLeaveSchema])
def get_doctor_leaves(
    doctor_id: int,
    hospital_id: int,
    db: Session = Depends(get_db),
    token_data: dict = Depends(get_token_payload),
):
    hospital_id = _authorized_hospital_id(hospital_id, token_data)
    doctor = db.query(Doctor).filter(
        Doctor.id == doctor_id,
        Doctor.hospital_id == hospital_id,
    ).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    return (
        db.query(DoctorLeave)
        .join(Doctor, Doctor.id == DoctorLeave.doctor_id)
        .filter(DoctorLeave.doctor_id == doctor_id, Doctor.hospital_id == hospital_id)
        .order_by(DoctorLeave.date)
        .all()
    )


@router.delete("/leaves/{leave_id}")
def delete_leave(
    leave_id: int,
    hospital_id: int,
    db: Session = Depends(get_db),
    token_data: dict = Depends(get_token_payload),
):
    hospital_id = _authorized_hospital_id(hospital_id, token_data)
    leave = (
        db.query(DoctorLeave)
        .join(Doctor, Doctor.id == DoctorLeave.doctor_id)
        .filter(DoctorLeave.id == leave_id, Doctor.hospital_id == hospital_id)
        .first()
    )
    if not leave:
        raise HTTPException(status_code=404, detail="Leave not found")

    db.delete(leave)
    db.commit()
    return {"status": "success"}
