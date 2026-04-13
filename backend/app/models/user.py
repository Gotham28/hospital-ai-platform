from sqlalchemy import Boolean, Column, Integer, String, ForeignKey # Added ForeignKey
from sqlalchemy.orm import relationship # Added relationship
from app.db.base_class import Base

class User(Base):
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean(), default=True)
    is_superuser = Column(Boolean(), default=False)
    role = Column(String, default="staff", nullable=False)
    # --- NEW: Multi-Tenancy Link ---
    hospital_id = Column(Integer, ForeignKey("hospital.id"), nullable=True) # Nullable for Superadmins
    hospital = relationship("Hospital", back_populates="users")