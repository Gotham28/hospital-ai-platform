from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.api.deps import get_db, get_current_tenant, get_token_payload
from app.models.lab_test import LabTest
from app.schemas.lab_test import LabTest as LabTestSchema, LabTestCreate, LabTestUpdate
import csv
import io
from fastapi import UploadFile, File
from app.models.hospital import Hospital
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
@router.post("/hospital/{hospital_id}/bulk-upload")
async def bulk_upload_lab_tests(
    hospital_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _tenant: int = Depends(get_current_tenant),
    token_data: dict = Depends(get_token_payload)
):
    if token_data.get("role") != "superadmin" and str(token_data.get("hospital_id")) != str(hospital_id):
        raise HTTPException(status_code=403, detail="Access denied")

    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    content = await file.read()
    stream = io.StringIO(content.decode("utf-8"))
    reader = csv.DictReader(stream)

    count = 0
    for row in reader:
        normalized_row = {k.strip().lower(): v.strip() for k, v in row.items()}
        
        name = normalized_row.get("name") or normalized_row.get("test name")
        if not name:
            continue

        # Parse boolean
        inhouse_str = normalized_row.get("is inhouse", "yes").lower()
        is_inhouse = inhouse_str in ["yes", "true", "1", "y", "in-house", "inhouse"]

        try:
            price = float(normalized_row.get("price", 0))
        except ValueError:
            price = 0.0

        test = LabTest(
            hospital_id=hospital_id,
            name=name,
            category=normalized_row.get("category", ""),
            price=price,
            prerequisites=normalized_row.get("prerequisites", ""),
            turnaround_time=normalized_row.get("turnaround time", ""),
            is_inhouse=is_inhouse
        )
        db.add(test)
        count += 1

    try:
        db.commit()
        return {"message": f"Successfully imported {count} lab tests."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")