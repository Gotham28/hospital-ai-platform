import uuid
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, UniqueConstraint, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.db.base_class import Base


def _generate_ref():
    return "APT-" + uuid.uuid4().hex[:6].upper()


class Appointment(Base):
    __tablename__ = "appointments"

    id               = Column(Integer, primary_key=True, index=True)
    reference_number = Column(String, unique=True, default=_generate_ref, nullable=False)
    hospital_id      = Column(Integer, ForeignKey("hospital.id"), nullable=False, index=True)
    doctor_id        = Column(Integer, ForeignKey("doctors.id"), nullable=False, index=True)
    patient_name     = Column(String, nullable=False)
    patient_age      = Column(String, nullable=False)   # stored as string ("32" or "32 years")
    patient_phone    = Column(String, nullable=False)
    preferred_date   = Column(String, nullable=False)   # "2026-04-15"
    time_of_day      = Column(String, nullable=False)   # "morning" | "afternoon" | "evening"

    # Staff fills these in when approving
    confirmed_time   = Column(String, nullable=True)    # "10:30 AM"

    # pending | approved | rejected
    status           = Column(String, default="pending", nullable=False, index=True)
    rejection_reason = Column(String, nullable=True)

    # Feature 4: relevance gate results — always written when relevance_criteria is set on the hospital
    # relevance_reason: the AI's plain-text explanation of its verdict (shown to staff in admin table)
    # needs_staff_review: True when AI wasn't confident, or patient doesn't match criteria
    relevance_reason      = Column(Text, nullable=True)
    needs_staff_review    = Column(Boolean, default=False, nullable=False)

    created_at       = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at       = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                              onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    hospital = relationship("Hospital")
    doctor   = relationship("Doctor")