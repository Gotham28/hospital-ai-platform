import csv
import io
import uuid
from sqlalchemy import func
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Body, UploadFile, File
from sqlalchemy.orm import Session
from datetime import datetime # Add this at the top
from app import crud, schemas
from app.api.deps import get_db, get_current_tenant
from app.models.hospital import Hospital
from app.models.doctor import Doctor
from app.availability import get_sheet_client # Ensure this is configured
from app.models.usage import UsageLedger
router = APIRouter()

# -------------------------------------------------
# 1. SUPER ADMIN ENDPOINTS
# -------------------------------------------------

@router.post("/", response_model=schemas.hospital.Hospital)
def create_hospital(
    *,
    db: Session = Depends(get_db),
    hospital_in: schemas.hospital.HospitalCreate,
):
    """Create a new hospital tenant."""
    hospital = crud.crud_hospital.get_hospital_by_slug(db, slug=hospital_in.slug)
    if hospital:
        raise HTTPException(
            status_code=400,
            detail="The hospital with this slug already exists in the system.",
        )
    return crud.crud_hospital.create_hospital(db=db, hospital=hospital_in)

@router.get("/", response_model=List[schemas.hospital.Hospital])
def read_hospitals(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
):
    """List all registered hospitals."""
    return crud.crud_hospital.get_hospitals(db, skip=skip, limit=limit)


# -------------------------------------------------
# 2. HOSPITAL MANAGEMENT (BY ID)
# -------------------------------------------------

@router.get("/{hospital_id}", response_model=schemas.hospital.Hospital)
def get_hospital_by_id(
    hospital_id: int, 
    db: Session = Depends(get_db)
):
    """Fetch specific hospital info."""
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")
    return hospital

@router.patch("/{hospital_id}")
def update_specific_hospital(
    hospital_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db)
):
    """Update settings for a specific hospital."""
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")
    
    # Update fields dynamically
    for key, value in payload.items():
        if hasattr(hospital, key):
            setattr(hospital, key, value)
    
    db.commit()
    db.refresh(hospital)
    return {"status": "success", "message": f"Settings for {hospital.name} updated."}


# -------------------------------------------------
# 3. DOCTOR MANAGEMENT (MULTI-TENANT)
# -------------------------------------------------

@router.get("/{hospital_id}/doctors")
def get_hospital_doctors(
    hospital_id: int, 
    db: Session = Depends(get_db)
):
    """Fetch the staff directory for a specific hospital."""
    return db.query(Doctor).filter(Doctor.hospital_id == hospital_id).all()

@router.post("/{hospital_id}/doctors")
def add_doctor(
    hospital_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db)
):
    """Add a single doctor manually."""
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    new_doc = Doctor(
        name=payload["name"],
        doctor_id=payload["doctor_id"],
        specialty=payload.get("specialty", "General Physician"),
        hospital_id=hospital_id
    )
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)
    return new_doc


# -------------------------------------------------
# 4. BULK UPLOAD & GOOGLE SHEET SYNC
# -------------------------------------------------

@router.post("/{hospital_id}/doctors/bulk-upload")
async def bulk_upload_and_sync(
    hospital_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # 1. Verify Hospital and Sheet
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital or not hospital.google_sheet_id:
        raise HTTPException(status_code=400, detail="Google Sheet ID not configured")

    # 2. Read and Parse CSV safely
    content = await file.read()
    stream = io.StringIO(content.decode("utf-8"))
    reader = csv.DictReader(stream) # Automatically uses the first row as headers
    
    sheet_rows = []
    for row in reader:
        # Normalize keys to handle case sensitivity and spaces
        normalized_row = {k.strip().lower(): v for k, v in row.items()}
        
        auto_id = f"H{hospital_id}-D-{uuid.uuid4().hex[:4].upper()}"
        
        # Robust mapping: checks for 'doctor name' or just 'name'
        name = normalized_row.get('doctor name') or normalized_row.get('name') or 'Unknown'
        dept = normalized_row.get('department') or 'General'
        schedule = normalized_row.get('base schedule') or normalized_row.get('schedule') or 'Not Specified'

        doctor = Doctor(
            doctor_id=auto_id,
            name=name,
            department=dept,
            base_schedule=schedule,
            hospital_id=hospital_id
        )
        db.add(doctor) # You were missing this db.add() in the code snippet!
        
        # Prepare for Google Sheet (ID, Name, Dept, Schedule, Absent, Available)
        sheet_rows.append([auto_id, name, dept, schedule, "", "Yes"])

    # 3. Sync to Google Sheets
    try:
        client = get_sheet_client()
        sheet = client.open_by_key(hospital.google_sheet_id).sheet1
        sheet.append_rows(sheet_rows)
        db.commit()
        return {"message": f"Successfully imported {len(sheet_rows)} doctors."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Google Sheet Sync Failed: {str(e)}")


# -------------------------------------------------
# 5. AUTH-BASED HELPERS (TENANT ADMIN)
# -------------------------------------------------

@router.get("/me", response_model=schemas.hospital.Hospital)
def get_my_hospital(
    db: Session = Depends(get_db), 
    hospital_id: int = Depends(get_current_tenant)
):
    """Get hospital info based on the admin's login token."""
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")
    return hospital

@router.patch("/me")
def update_hospital_settings(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    hospital_id: int = Depends(get_current_tenant)
):
    """Update settings for the logged-in admin's hospital."""
    return update_specific_hospital(hospital_id=hospital_id, payload=payload, db=db)

@router.get("/slug/{slug}")
def get_hospital_by_slug(slug: str, db: Session = Depends(get_db)):
    hospital = db.query(Hospital).filter(Hospital.slug == slug).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")
    # Return everything the patient site needs
    return {
        "id": hospital.id, 
        "name": hospital.name, 
        "google_sheet_id": hospital.google_sheet_id
    }


@router.get("/{hospital_id}/billing")
async def get_hospital_billing(hospital_id: int, db: Session = Depends(get_db)):
    # Calculate start of current month
    first_day = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    stats = db.query(
        func.sum(UsageLedger.total_tokens).label("tokens"),
        func.sum(UsageLedger.estimated_cost).label("cost"),
        func.count(UsageLedger.id).label("total_chats")
    ).filter(
        UsageLedger.hospital_id == hospital_id,
        UsageLedger.created_at >= first_day
    ).first()

    # Calculation logic for your markup
    raw_cost = stats.cost or 0.0
    margin_multiplier = 5.0  # 500% markup (standard for SaaS)
    platform_fee_inr = 2500.0 # Base monthly platform fee
    
    return {
        "period": first_day.strftime("%B %Y"),
        "usage": {
            "total_chats": stats.total_chats or 0,
            "tokens_consumed": stats.tokens or 0,
            "raw_cost_usd": round(raw_cost, 4),
        },
        "estimated_invoice_inr": round(platform_fee_inr + (raw_cost * 83 * margin_multiplier), 2)
    }