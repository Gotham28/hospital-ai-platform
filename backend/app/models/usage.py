from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from datetime import datetime, timezone
from app.db.base_class import Base

class UsageLedger(Base):
    __tablename__ = "usage_ledger"
    
    id = Column(Integer, primary_key=True, index=True)
    hospital_id = Column(Integer, ForeignKey("hospital.id"))
    endpoint = Column(String)  # e.g., "/chat" or "/ingest"
    prompt_tokens = Column(Integer)
    completion_tokens = Column(Integer)
    total_tokens = Column(Integer)
    estimated_cost = Column(Float) 
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))