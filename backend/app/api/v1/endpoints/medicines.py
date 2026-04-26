from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.api.deps import get_db, get_current_tenant, get_token_payload
from app.models.medicine import Medicine
from app.schemas.medicine import Medicine as MedicineSchema, MedicineCreate, MedicineUpdate
import csv
import io
from fastapi import UploadFile, File
from app.models.hospital import Hospital
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
@router.post("/hospital/{hospital_id}/bulk-upload")
async def bulk_upload_medicines(
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
        # Clean keys to lowercase for easier matching
        normalized_row = {k.strip().lower(): v.strip() for k, v in row.items()}
        
        name = normalized_row.get("name") or normalized_row.get("generic name")
        if not name:
            continue # Skip empty rows

        # Parse boolean values safely
        req_rx_str = normalized_row.get("requires prescription", "no").lower()
        requires_prescription = req_rx_str in ["yes", "true", "1", "y"]

        # Parse price safely
        try:
            price = float(normalized_row.get("price", 0))
        except ValueError:
            price = 0.0

        med = Medicine(
            hospital_id=hospital_id,
            name=name,
            brand_name=normalized_row.get("brand name", ""),
            category=normalized_row.get("category", ""),
            price=price,
            stock_status=normalized_row.get("stock status", "in_stock").lower().replace(" ", "_"),
            requires_prescription=requires_prescription
        )
        db.add(med)
        count += 1

    try:
        db.commit()
        return {"message": f"Successfully imported {count} medicines."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")