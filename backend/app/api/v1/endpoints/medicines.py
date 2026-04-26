from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.api.deps import get_db, get_current_tenant, get_token_payload
from app.models.medicine import Medicine
from app.schemas.medicine import Medicine as MedicineSchema, MedicineCreate, MedicineUpdate

router = APIRouter()

@router.post("/", response_model=MedicineSchema)
def create_medicine(
    payload: MedicineCreate, 
    db: Session = Depends(get_db),
    _tenant: int = Depends(get_current_tenant),
    token_data: dict = Depends(get_token_payload)
):
    if token_data.get("role") != "superadmin" and str(token_data.get("hospital_id")) != str(payload.hospital_id):
        raise HTTPException(status_code=403, detail="Access denied")

    db_item = Medicine(**payload.model_dump())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

@router.get("/hospital/{hospital_id}", response_model=List[MedicineSchema])
def list_medicines(
    hospital_id: int, 
    db: Session = Depends(get_db),
    _tenant: int = Depends(get_current_tenant),
    token_data: dict = Depends(get_token_payload)
):
    if token_data.get("role") != "superadmin" and str(token_data.get("hospital_id")) != str(hospital_id):
        raise HTTPException(status_code=403, detail="Access denied")

    return db.query(Medicine).filter(Medicine.hospital_id == hospital_id).all()

@router.delete("/{medicine_id}")
def delete_medicine(
    medicine_id: int, 
    db: Session = Depends(get_db),
    _tenant: int = Depends(get_current_tenant)
):
    db_item = db.query(Medicine).filter(Medicine.id == medicine_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Medicine not found")
    
    db.delete(db_item)
    db.commit()
    return {"status": "success"}