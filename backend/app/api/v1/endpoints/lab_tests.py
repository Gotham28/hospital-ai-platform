from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.api.deps import get_db, get_current_tenant, get_token_payload
from app.models.lab_test import LabTest
from app.schemas.lab_test import LabTest as LabTestSchema, LabTestCreate, LabTestUpdate

router = APIRouter()

@router.post("/", response_model=LabTestSchema)
def create_lab_test(
    payload: LabTestCreate, 
    db: Session = Depends(get_db),
    _tenant: int = Depends(get_current_tenant),
    token_data: dict = Depends(get_token_payload)
):
    if token_data.get("role") != "superadmin" and str(token_data.get("hospital_id")) != str(payload.hospital_id):
        raise HTTPException(status_code=403, detail="Access denied")

    db_item = LabTest(**payload.model_dump())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

@router.get("/hospital/{hospital_id}", response_model=List[LabTestSchema])
def list_lab_tests(
    hospital_id: int, 
    db: Session = Depends(get_db),
    _tenant: int = Depends(get_current_tenant),
    token_data: dict = Depends(get_token_payload)
):
    if token_data.get("role") != "superadmin" and str(token_data.get("hospital_id")) != str(hospital_id):
        raise HTTPException(status_code=403, detail="Access denied")

    return db.query(LabTest).filter(LabTest.hospital_id == hospital_id).all()

@router.delete("/{test_id}")
def delete_lab_test(
    test_id: int, 
    db: Session = Depends(get_db),
    _tenant: int = Depends(get_current_tenant)
):
    db_item = db.query(LabTest).filter(LabTest.id == test_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Lab test not found")
    
    db.delete(db_item)
    db.commit()
    return {"status": "success"}