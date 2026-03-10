from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base_class import Base

class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(String, index=True, nullable=False)
    name = Column(String, nullable=False)
    # Add these two missing columns:
    department = Column(String, nullable=True) 
    base_schedule = Column(String, nullable=True)
    
    hospital_id = Column(Integer, ForeignKey("hospital.id"), nullable=False)
    hospital = relationship("Hospital", back_populates="doctors")