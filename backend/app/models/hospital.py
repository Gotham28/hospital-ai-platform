from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base

class Hospital(Base):
    __tablename__ = "hospital"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    slug = Column(String, unique=True, index=True, nullable=False) # e.g., "apollo-delhi" for URLs
    address = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    system_prompt = Column(Text, default="You are Arogya, a helpful assistant for a specialty hospital.")
    is_active = Column(Boolean, default=True)
    # Add this column to your existing Hospital class
    google_sheet_id = Column(String, nullable=True)
    # Relationship: One Hospital has many Users
    users = relationship("User", back_populates="hospital")
    # Inside your Hospital class in app/models/hospital.py
    doctors = relationship("Doctor", back_populates="hospital", cascade="all, delete-orphan")