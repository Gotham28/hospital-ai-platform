from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base_class import Base

class Medicine(Base):
    __tablename__ = "medicines"
    
    id = Column(Integer, primary_key=True, index=True)
    hospital_id = Column(Integer, ForeignKey("hospital.id"), nullable=False, index=True)
    name = Column(String, nullable=False, index=True)
    brand_name = Column(String, nullable=True)
    category = Column(String, nullable=True)
    price = Column(Float, nullable=True)
    stock_status = Column(String, default="in_stock") # in_stock, out_of_stock, low_stock
    requires_prescription = Column(Boolean, default=False)
    
    hospital = relationship("Hospital")