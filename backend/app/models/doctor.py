from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base_class import Base
from pgvector.sqlalchemy import Vector  # ADD THIS


class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(String, index=True, nullable=False)
    name = Column(String, nullable=False)
    # Add these two missing columns:
    department = Column(String, nullable=True) 
    base_schedule = Column(String, nullable=True)
    embedding = Column(Vector(1536), nullable=True)  # ADD THIS

    
    hospital_id = Column(Integer, ForeignKey("hospital.id"), nullable=False)
    hospital = relationship("Hospital", back_populates="doctors")
    schedules = relationship("DoctorSchedule", back_populates="doctor", cascade="all, delete-orphan")
    leaves = relationship("DoctorLeave", back_populates="doctor", cascade="all, delete-orphan")