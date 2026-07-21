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
    # Feature 3: outsourced lab test flag (IRIS clinic, 2026-07-21)
    # is_outsourced: admin-toggleable per test; defaults to False (no change to existing rows).
    # outsourced_note: free-text note shown by the AI when this test is mentioned.
    #   TODO: left empty by default — wording pending sign-off from Iris Rheumatology Clinic.
    is_outsourced = Column(Boolean, nullable=False, default=False)
    outsourced_note = Column(Text, nullable=True)
    
    hospital = relationship("Hospital")