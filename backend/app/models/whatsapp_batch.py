from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, LargeBinary, String, UniqueConstraint

from app.db.base_class import Base


class WhatsAppBatchItem(Base):
    __tablename__ = "whatsapp_batch_items"
    __table_args__ = (
        UniqueConstraint("hospital_id", "batch_id", "position", name="uq_whatsapp_batch_position"),
        Index("ix_whatsapp_batch_ready", "status", "available_at"),
        Index("ix_whatsapp_batch_recipient", "hospital_id", "recipient_hash", "status"),
    )

    id = Column(Integer, primary_key=True)
    hospital_id = Column(Integer, ForeignKey("hospital.id", ondelete="CASCADE"), nullable=False)
    batch_id = Column(String(36), nullable=False)
    position = Column(Integer, nullable=False)
    actor_hash = Column(String(64), nullable=False)
    approval_hash = Column(String(64), nullable=False)
    recipient_hash = Column(String(64), nullable=False)
    encrypted_phone = Column(LargeBinary)
    masked_phone = Column(String(40), nullable=False)
    language = Column(String(8), nullable=False)
    status = Column(String(24), nullable=False)
    message_id = Column(Integer, ForeignKey("whatsapp_logs.id", ondelete="SET NULL"))
    available_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    claim_id = Column(String(36))
