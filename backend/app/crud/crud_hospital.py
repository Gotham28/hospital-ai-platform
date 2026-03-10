from sqlalchemy.orm import Session
from app.models.hospital import Hospital
from app.schemas.hospital import HospitalCreate

def get_hospital(db: Session, hospital_id: int):
    return db.query(Hospital).filter(Hospital.id == hospital_id).first()

def get_hospital_by_slug(db: Session, slug: str):
    return db.query(Hospital).filter(Hospital.slug == slug).first()

def get_hospitals(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Hospital).offset(skip).limit(limit).all()

def create_hospital(db: Session, hospital: HospitalCreate):
    db_obj = Hospital(
        name=hospital.name,
        slug=hospital.slug,
        address=hospital.address,
        is_active=hospital.is_active
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj