from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, UniqueConstraint
from datetime import datetime, timezone
from app.db.base_class import Base

class WhatsAppLog(Base):
    __tablename__ = "whatsapp_logs"
    __table_args__ = (
        UniqueConstraint("hospital_id", "request_id", name="uq_whatsapp_hospital_request"),
        UniqueConstraint("provider_message_id", name="uq_whatsapp_provider_message"),
    )

    id = Column(Integer, primary_key=True, index=True)
    hospital_id = Column(Integer, ForeignKey("hospital.id"), nullable=False, index=True)
    masked_phone = Column(String, nullable=False)
    status = Column(String, nullable=False)
    error_message = Column(String, nullable=True)
    twilio_sid = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Nullable additions preserve existing Twilio rows and their original status.
    provider = Column(String(16), nullable=True)
    provider_message_id = Column(String(255), nullable=True)
    request_id = Column(String(36), nullable=True)
    request_fingerprint = Column(String(64), nullable=True)
    language = Column(String(8), nullable=True)
    consent_confirmed_at = Column(DateTime(timezone=True), nullable=True)
    consent_recorded_by = Column(String(64), nullable=True)  # keyed hash of staff JWT subject
    error_code = Column(String(64), nullable=True)
    status_updated_at = Column(DateTime(timezone=True), nullable=True)
    provider_event_at = Column(DateTime(timezone=True), nullable=True)
