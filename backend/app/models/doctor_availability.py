from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Date
from sqlalchemy.orm import relationship
from app.db.base_class import Base

class DoctorSchedule(Base):
    __tablename__ = "doctor_schedules"
    
    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False, index=True)
    day_of_week = Column(Integer, nullable=False) # 0=Monday, 1=Tuesday, ..., 6=Sunday
    start_time = Column(String, nullable=False)   # e.g., "09:00"
    end_time = Column(String, nullable=False)     # e.g., "17:00"
    is_active = Column(Boolean, default=True)
    
    doctor = relationship("Doctor", back_populates="schedules")

class DoctorLeave(Base):
    __tablename__ = "doctor_leaves"
    
    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    reason = Column(String, nullable=True)
    
    doctor = relationship("Doctor", back_populates="leaves")