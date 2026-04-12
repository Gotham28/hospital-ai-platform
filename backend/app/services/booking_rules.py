"""
app/services/booking_rules.py

Validates a booking request against per-hospital configuration stored
in hospital.booking_config (JSON column).

Default config (used when booking_config is None or missing a key):
{
    "bookable_departments": [],        # empty = all departments allowed
    "min_advance_hours": 2,
    "max_per_doctor_per_day": 20,
    "notification_email": "",
    "reminder_hours_before": 24
}
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy.orm import Session
from app.models.appointment import Appointment
from app.models.doctor import Doctor
from app.models.hospital import Hospital

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "bookable_departments": [],
    "min_advance_hours": 2,
    "max_per_doctor_per_day": 20,
    "notification_email": "",
    "reminder_hours_before": 24,
}


def get_booking_config(hospital: Hospital) -> dict:
    raw = getattr(hospital, "booking_config", None)
    if not raw:
        return DEFAULT_CONFIG.copy()
    try:
        cfg = json.loads(raw) if isinstance(raw, str) else raw
        return {**DEFAULT_CONFIG, **cfg}
    except Exception:
        return DEFAULT_CONFIG.copy()


def validate_booking(
    hospital: Hospital,
    doctor: Doctor,
    preferred_date: str,   # "YYYY-MM-DD"
    db: Session,
) -> tuple[bool, Optional[str]]:
    """
    Returns (ok, error_message).
    ok=True means the booking can proceed.
    """
    config = get_booking_config(hospital)

    # 1. Check department is bookable
    allowed_depts = config.get("bookable_departments", [])
    if allowed_depts:
        dept = (doctor.department or "").lower()
        if not any(dept == a.lower() for a in allowed_depts):
            return False, (
                f"Online booking is not available for {doctor.department}. "
                "Please call the reception desk."
            )

    # 2. Check minimum advance notice
    min_hours = config.get("min_advance_hours", 2)
    try:
        appt_date = datetime.strptime(preferred_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        if (appt_date - now) < timedelta(hours=min_hours):
            return False, (
                f"Appointments must be booked at least {min_hours} hours in advance. "
                "Please choose a later date."
            )
    except ValueError:
        return False, "Invalid date format. Please use YYYY-MM-DD."

    # 3. Check doctor daily slot limit
    max_per_day = config.get("max_per_doctor_per_day", 20)
    existing_count = (
        db.query(Appointment)
        .filter(
            Appointment.doctor_id == doctor.id,
            Appointment.preferred_date == preferred_date,
            Appointment.status != "rejected",
        )
        .count()
    )
    if existing_count >= max_per_day:
        return False, (
            f"Dr. {doctor.name} has no more slots available on {preferred_date}. "
            "Please choose another date or doctor."
        )

    return True, None