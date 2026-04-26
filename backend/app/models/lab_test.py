from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.db.base_class import Base

class LabTest(Base):
    __tablename__ = "lab_tests"
    
    id = Column(Integer, primary_key=True, index=True)
    hospital_id = Column(Integer, ForeignKey("hospital.id"), nullable=False, index=True)
    name = Column(String, nullable=False, index=True)
    category = Column(String, nullable=True)
    price = Column(Float, nullable=True)
    prerequisites = Column(Text, nullable=True) # e.g., "Fasting for 8 hours"
    turnaround_time = Column(String, nullable=True)
    is_inhouse = Column(Boolean, default=True)
    
    hospital = relationship("Hospital")