"""
app/api/v1/endpoints/appointments.py

All appointment-related REST endpoints consumed by:
  - The admin dashboard (list, approve, reject, config)
  - The chat bot via ai.py (create, status check)
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_tenant
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.hospital import Hospital
from app.services.booking_rules import validate_booking, get_booking_config
from app.services.email import notify_staff_new_appointment, notify_patient_approved

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# SCHEMAS
# =============================================================================

class AppointmentCreate(BaseModel):
    hospital_id: int
    doctor_id: int
    patient_name: str
    patient_age: str
    patient_phone: str
    preferred_date: str   # "YYYY-MM-DD"
    time_of_day: str      # "morning" | "afternoon" | "evening"


class ApprovePayload(BaseModel):
    confirmed_time: str   # e.g. "10:30 AM"


class RejectPayload(BaseModel):
    reason: str


class BookingConfigPayload(BaseModel):
    bookable_departments: list[str] = []
    min_advance_hours: int = 2
    max_per_doctor_per_day: int = 20
    notification_email: str = ""
    reminder_hours_before: int = 24


# =============================================================================
# CREATE — called by the chatbot after patient confirms
# =============================================================================

@router.post("/")
def create_appointment(payload: AppointmentCreate, db: Session = Depends(get_db)):
    hospital = db.query(Hospital).filter(Hospital.id == payload.hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    doctor = db.query(Doctor).filter(
        Doctor.id == payload.doctor_id,
        Doctor.hospital_id == payload.hospital_id
    ).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    # Validate against per-hospital booking rules
    ok, error = validate_booking(hospital, doctor, payload.preferred_date, db)
    if not ok:
        raise HTTPException(status_code=400, detail=error)

    appt = Appointment(
        hospital_id=payload.hospital_id,
        doctor_id=payload.doctor_id,
        patient_name=payload.patient_name,
        patient_age=payload.patient_age,
        patient_phone=payload.patient_phone,
        preferred_date=payload.preferred_date,
        time_of_day=payload.time_of_day,
        status="pending",
    )
    db.add(appt)
    db.commit()
    db.refresh(appt)

    # Fire staff notification email (non-blocking — failure doesn't break booking)
    config = get_booking_config(hospital)
    staff_email = config.get("notification_email", "")
    if staff_email:
        notify_staff_new_appointment(
            staff_email=staff_email,
            hospital_name=hospital.name,
            reference=appt.reference_number,
            patient_name=appt.patient_name,
            patient_age=appt.patient_age,
            patient_phone=appt.patient_phone,
            doctor_name=doctor.name,
            preferred_date=appt.preferred_date,
            time_of_day=appt.time_of_day,
        )

    return {
        "reference_number": appt.reference_number,
        "status": appt.status,
        "message": "Appointment request submitted. The hospital will call you to confirm.",
    }


# =============================================================================
# LIST — admin dashboard
# =============================================================================

@router.get("/hospital/{hospital_id}")
def list_appointments(
    hospital_id: int,
    status: Optional[str] = None,   # filter: pending | approved | rejected
    db: Session = Depends(get_db),
    _tenant: int = Depends(get_current_tenant),
):
    q = db.query(Appointment).filter(Appointment.hospital_id == hospital_id)
    if status:
        q = q.filter(Appointment.status == status)
    appts = q.order_by(Appointment.created_at.desc()).all()

    results = []
    for a in appts:
        doctor = db.query(Doctor).filter(Doctor.id == a.doctor_id).first()
        results.append({
            "id": a.id,
            "reference_number": a.reference_number,
            "patient_name": a.patient_name,
            "patient_age": a.patient_age,
            "patient_phone": a.patient_phone,
            "doctor_name": doctor.name if doctor else "Unknown",
            "doctor_department": doctor.department if doctor else "",
            "preferred_date": a.preferred_date,
            "time_of_day": a.time_of_day,
            "status": a.status,
            "confirmed_time": a.confirmed_time,
            "rejection_reason": a.rejection_reason,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        })
    return results


# =============================================================================
# APPROVE
# =============================================================================

@router.patch("/{appointment_id}/approve")
def approve_appointment(
    appointment_id: int,
    payload: ApprovePayload,
    db: Session = Depends(get_db),
    _tenant: int = Depends(get_current_tenant),
):
    appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if appt.status != "pending":
        raise HTTPException(status_code=400, detail=f"Appointment is already {appt.status}")

    appt.status = "approved"
    appt.confirmed_time = payload.confirmed_time
    appt.updated_at = datetime.now(timezone.utc)
    db.commit()

    # Email staff to call patient
    hospital = db.query(Hospital).filter(Hospital.id == appt.hospital_id).first()
    doctor   = db.query(Doctor).filter(Doctor.id == appt.doctor_id).first()
    if hospital:
        config = get_booking_config(hospital)
        staff_email = config.get("notification_email", "")
        if staff_email:
            notify_patient_approved(
                staff_email=staff_email,
                hospital_name=hospital.name,
                reference=appt.reference_number,
                patient_name=appt.patient_name,
                patient_phone=appt.patient_phone,
                doctor_name=doctor.name if doctor else "Doctor",
                confirmed_time=payload.confirmed_time,
                preferred_date=appt.preferred_date,
            )

    return {"status": "approved", "confirmed_time": payload.confirmed_time}


# =============================================================================
# REJECT
# =============================================================================

@router.patch("/{appointment_id}/reject")
def reject_appointment(
    appointment_id: int,
    payload: RejectPayload,
    db: Session = Depends(get_db),
    _tenant: int = Depends(get_current_tenant),
):
    appt = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if appt.status != "pending":
        raise HTTPException(status_code=400, detail=f"Appointment is already {appt.status}")

    appt.status = "rejected"
    appt.rejection_reason = payload.reason
    appt.updated_at = datetime.now(timezone.utc)
    db.commit()

    return {"status": "rejected", "reason": payload.reason}


# =============================================================================
# STATUS CHECK — patient checks via bot using phone + hospital
# =============================================================================

@router.get("/status/{hospital_id}/{phone}")
def get_appointment_status(
    hospital_id: int,
    phone: str,
    db: Session = Depends(get_db),
):
    appts = (
        db.query(Appointment)
        .filter(
            Appointment.hospital_id == hospital_id,
            Appointment.patient_phone == phone,
        )
        .order_by(Appointment.created_at.desc())
        .limit(3)
        .all()
    )
    if not appts:
        return {"found": False, "message": "No appointments found for this phone number."}

    results = []
    for a in appts:
        doctor = db.query(Doctor).filter(Doctor.id == a.doctor_id).first()
        results.append({
            "reference_number": a.reference_number,
            "doctor_name": doctor.name if doctor else "Unknown",
            "preferred_date": a.preferred_date,
            "time_of_day": a.time_of_day,
            "status": a.status,
            "confirmed_time": a.confirmed_time,
            "rejection_reason": a.rejection_reason,
        })

    return {"found": True, "appointments": results}


# =============================================================================
# BOOKING CONFIG — per-hospital rules (admin only)
# =============================================================================

@router.get("/config/{hospital_id}")
def get_booking_config_endpoint(
    hospital_id: int,
    db: Session = Depends(get_db),
    _tenant: int = Depends(get_current_tenant),
):
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")
    return get_booking_config(hospital)


@router.patch("/config/{hospital_id}")
def update_booking_config(
    hospital_id: int,
    payload: BookingConfigPayload,
    db: Session = Depends(get_db),
    _tenant: int = Depends(get_current_tenant),
):
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")
    hospital.booking_config = json.dumps(payload.model_dump())
    db.commit()
    return {"status": "success", "config": payload.model_dump()}