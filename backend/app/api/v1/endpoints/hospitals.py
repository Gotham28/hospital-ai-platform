import csv
import io
import uuid
from sqlalchemy import func
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Body, UploadFile, File
from sqlalchemy.orm import Session
from datetime import datetime
from app import crud, schemas
from app.api.deps import get_db, get_current_tenant, require_superadmin
from app.models.hospital import Hospital
from app.models.doctor import Doctor
from app.models.usage import UsageLedger

router = APIRouter()

# =============================================================================
# FIX #3: ROUTE ORDER — Static/named routes MUST come before /{hospital_id}.
# FastAPI matches routes top-to-bottom. If /{hospital_id} is registered first,
# it will intercept GET /me and GET /slug/arogya and try to cast the string as
# an int, returning a 422 before the correct handler is ever reached.
# =============================================================================


# -------------------------------------------------
# 1. STATIC NAMED ROUTES (must be first)
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
def update_my_hospital_settings(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    hospital_id: int = Depends(get_current_tenant)
):
    """Update settings for the logged-in admin's hospital."""
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")
    for key, value in payload.items():
        if hasattr(hospital, key):
            setattr(hospital, key, value)
    db.commit()
    db.refresh(hospital)
    return {"status": "success", "message": f"Settings for {hospital.name} updated."}

@router.get("/slug/{slug}")
def get_hospital_by_slug(slug: str, db: Session = Depends(get_db)):
    """Public endpoint: resolve a slug to hospital id + name for ThemeLoader."""
    hospital = db.query(Hospital).filter(Hospital.slug == slug).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")
    return {
        "id": hospital.id,
        "name": hospital.name,
        "google_sheet_id": hospital.google_sheet_id
    }


# -------------------------------------------------
# 2. COLLECTION ROUTES
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
# 3. PARAMETERISED ROUTES (must be last)
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
    db: Session = Depends(get_db),
    # FIX #4: Added auth guard. Without this, any unauthenticated caller
    # knowing a sequential hospital_id could overwrite system_prompt or
    # google_sheet_id. Now requires a valid JWT.
    _current_tenant: int = Depends(get_current_tenant),
):
    """Update settings for a specific hospital (requires auth)."""
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    for key, value in payload.items():
        if hasattr(hospital, key):
            setattr(hospital, key, value)

    db.commit()
    db.refresh(hospital)
    return {"status": "success", "message": f"Settings for {hospital.name} updated."}

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
        department=payload.get("department", "General Physician"),
        hospital_id=hospital_id
    )
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)
    return new_doc

@router.post("/{hospital_id}/doctors/bulk-upload")
async def bulk_upload_and_sync(
    hospital_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    from openai import OpenAI
    import os
    oai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    content = await file.read()
    stream = io.StringIO(content.decode("utf-8"))
    reader = csv.DictReader(stream)

    doctors_to_embed = []
    count = 0
    for row in reader:
        normalized_row = {k.strip().lower(): v for k, v in row.items()}
        auto_id = f"H{hospital_id}-D-{uuid.uuid4().hex[:4].upper()}"
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
        db.add(doctor)
        doctors_to_embed.append((doctor, name, dept, schedule))
        count += 1

    db.flush()  # assigns IDs without committing

    # Embed in batch
    texts = [
        f"Dr. {name}, {dept} specialist, schedule: {schedule}"
        for _, name, dept, schedule in doctors_to_embed
    ]
    if texts:
        resp = oai.embeddings.create(input=texts, model="text-embedding-3-small")
        for (doctor, _, _, _), emb in zip(doctors_to_embed, resp.data):
            doctor.embedding = emb.embedding

    try:
        db.commit()
        return {"message": f"Successfully imported and embedded {count} doctors."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database Sync Failed: {str(e)}")

@router.get("/{hospital_id}/billing")
async def get_hospital_billing(hospital_id: int, db: Session = Depends(get_db)):
    first_day = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    stats = db.query(
        func.sum(UsageLedger.total_tokens).label("tokens"),
        func.sum(UsageLedger.estimated_cost).label("cost"),
        func.count(UsageLedger.id).label("total_chats")
    ).filter(
        UsageLedger.hospital_id == hospital_id,
        UsageLedger.created_at >= first_day
    ).first()

    raw_cost = stats.cost or 0.0
    margin_multiplier = 5.0
    platform_fee_inr = 2500.0
    total_due_inr = round(platform_fee_inr + (raw_cost * 83 * margin_multiplier), 2)

    # FIX #5: Reshaped response to match what HospitalStats.tsx actually reads.
    # Frontend expects billing.invoice.total_due_inr and billing.invoice.platform_fee.
    # Old backend returned estimated_invoice_inr at the top level — key mismatch.
    return {
        "period": first_day.strftime("%B %Y"),
        "usage": {
            "total_chats": stats.total_chats or 0,
            "tokens_consumed": stats.tokens or 0,
            "raw_cost_usd": round(raw_cost, 4),
        },
        "invoice": {
            "total_due_inr": total_due_inr,
            "platform_fee": platform_fee_inr,
        }
    }

@router.post("/{hospital_id}/staff")
def create_staff_account(
    hospital_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    _: str = Depends(require_superadmin),   # only you can do this
):
    from app.models.user import User
    from app.crud.crud_user import get_password_hash   # or however your hashing works
    
    existing = db.query(User).filter(User.email == payload["email"]).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user = User(
        full_name=payload["full_name"],
        email=payload["email"],
        hashed_password=get_password_hash(payload["password"]),
        hospital_id=hospital_id,
        role="staff",
        is_active=True,
    )
    db.add(user)
    db.commit()
    return {"status": "success", "email": user.email}