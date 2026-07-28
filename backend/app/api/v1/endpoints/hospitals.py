import csv
import io
import uuid
import json # Ensure this is imported at the top
import os        # ← ADD
import logging   # ← ADD
from openai import OpenAI   # ← ADD
from app.core.config import settings

logger = logging.getLogger(__name__)
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
    doctors = db.query(Doctor).filter(Doctor.hospital_id == hospital_id).all()
    
    # Return a formatted dict, leaving behind the 'embedding' column
    return [
        {
            "id": d.id,
            "doctor_id": d.doctor_id,
            "name": d.name,
            "department": d.department,
            "base_schedule": d.base_schedule,
        }
        for d in doctors
    ]

@router.post("/{hospital_id}/doctors")
def add_doctor(hospital_id: int, payload: dict = Body(...), db: Session = Depends(get_db)):
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    new_doc = Doctor(
        name=payload["name"],
        doctor_id=payload["doctor_id"],
        department=payload.get("department", "General Physician"),
        base_schedule=payload.get("base_schedule"),
        hospital_id=hospital_id
    )
    db.add(new_doc)
    db.flush()  # get the ID without committing

    # Auto-embed so the AI can find this doctor immediately
    try:
        oai = OpenAI(api_key=settings.OPENAI_API_KEY)
        text = f"Dr. {new_doc.name}, {new_doc.department} specialist"
        resp = oai.embeddings.create(input=[text], model="text-embedding-3-small")
        new_doc.embedding = resp.data[0].embedding
    except Exception as e:
        logger.warning(f"Embedding failed for new doctor: {e}")  # non-fatal

    db.commit()
    db.refresh(new_doc)
    return {
        "id": new_doc.id,
        "doctor_id": new_doc.doctor_id,
        "name": new_doc.name,
        "department": new_doc.department,
        "base_schedule": new_doc.base_schedule,
    }
@router.post("/{hospital_id}/doctors/bulk-upload")
async def bulk_upload_and_sync(
    hospital_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    from openai import OpenAI
    import os
    oai = OpenAI(api_key=settings.OPENAI_API_KEY)

    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    content = await file.read()
    text_content = content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text_content))
    csv_headers = reader.fieldnames
    
    if not csv_headers:
        raise HTTPException(status_code=400, detail="CSV is empty.")

    target_schema = {
        "name": "Doctor's name (Required)",
        "department": "Department or specialty",
        "base_schedule": "General working hours, availability, or schedule"
    }

    prompt = f"""
    Map these CSV headers: {csv_headers}
    To this schema: {json.dumps(target_schema)}
    Return ONLY a raw JSON object where keys are the schema keys and values are the exact matching string from the CSV headers. Null if no match.
    """

    llm_resp = oai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": prompt}],
        response_format={"type": "json_object"}
    )
    mapping = json.loads(llm_resp.choices[0].message.content)

    doctors_to_embed = []
    count = 0
    for row in reader:
        name_col = mapping.get("name")
        if not name_col or not row.get(name_col):
            continue

        dept_col = mapping.get("department")
        sched_col = mapping.get("base_schedule")
        
        name = row.get(name_col).strip()
        dept = row.get(dept_col, "General").strip() if dept_col else "General"
        schedule = row.get(sched_col, "Not Specified").strip() if sched_col else "Not Specified"
        auto_id = f"H{hospital_id}-D-{uuid.uuid4().hex[:4].upper()}"

        doctor = Doctor(doctor_id=auto_id, name=name, department=dept, base_schedule=schedule, hospital_id=hospital_id)
        db.add(doctor)
        doctors_to_embed.append((doctor, name, dept, schedule))
        count += 1

    db.flush()

    # Bulk generate embeddings so the AI can route patients to them
    texts = [f"Dr. {name}, {dept} specialist, schedule: {schedule}" for _, name, dept, schedule in doctors_to_embed]
    if texts:
        resp = oai.embeddings.create(input=texts, model="text-embedding-3-small")
        for (doctor, _, _, _), emb in zip(doctors_to_embed, resp.data):
            doctor.embedding = emb.embedding

    try:
        db.commit()
        return {"message": f"Successfully imported, mapped, and embedded {count} doctors."}
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
@router.delete("/{hospital_id}/doctors/{doctor_id}")
def delete_doctor(hospital_id: int, doctor_id: int, db: Session = Depends(get_db)):
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id, Doctor.hospital_id == hospital_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    db.delete(doctor)
    db.commit()
    return {"status": "success"}

@router.patch("/{hospital_id}/doctors/{doctor_id}")
def update_doctor(hospital_id: int, doctor_id: int, payload: dict = Body(...), db: Session = Depends(get_db)):
    doctor = db.query(Doctor).filter(Doctor.id == doctor_id, Doctor.hospital_id == hospital_id).first()
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    needs_reembed = any(k in payload for k in ("name", "department", "base_schedule"))
    for key, value in payload.items():
        if hasattr(doctor, key):
            setattr(doctor, key, value)

    if needs_reembed:
        try:
            from openai import OpenAI
            oai = OpenAI(api_key=settings.OPENAI_API_KEY)
            text = f"Dr. {doctor.name}, {doctor.department} specialist, schedule: {doctor.base_schedule or ''}"
            resp = oai.embeddings.create(input=[text], model="text-embedding-3-small")
            doctor.embedding = resp.data[0].embedding
        except Exception as e:
            logger.warning(f"Re-embedding failed: {e}")

    db.commit()
    db.refresh(doctor)
    return doctor
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

@router.delete("/{hospital_id}/billing/reset")
def reset_hospital_billing(hospital_id: int, db: Session = Depends(get_db)):
    db.query(UsageLedger).filter(UsageLedger.hospital_id == hospital_id).delete()
    db.commit()
    return {"status": "success", "message": "Billing cycle reset successfully"}

"""
ADD THIS ENDPOINT to backend/app/api/v1/endpoints/hospitals.py

Place it in the "PARAMETERISED ROUTES" section, after the existing
@router.delete("/{hospital_id}/billing/reset") endpoint.

It hard-deletes a hospital and all its related data (doctors,
knowledge base, appointments, users) using a single CASCADE-aware
DELETE. Only a superadmin can call this.
"""

@router.delete("/{hospital_id}")
def delete_hospital(
    hospital_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_superadmin),   # superadmin only
):
    """
    Permanently delete a hospital and ALL its associated data:
    doctors, knowledge base entries, appointments, and staff accounts.
    
    This is irreversible. The frontend must show a confirmation dialog.
    """
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    # Manually delete related data for tables that don't have
    # cascade="all, delete-orphan" set on the Hospital model yet.
    # (Doctors already have cascade, but the others may not.)
    from app.models.appointment import Appointment
    from app.models.knowledge import KnowledgeBase
    from app.models.user import User
    from app.models.usage import UsageLedger

    db.query(Appointment).filter(Appointment.hospital_id == hospital_id).delete()
    db.query(KnowledgeBase).filter(KnowledgeBase.hospital_id == hospital_id).delete()
    db.query(UsageLedger).filter(UsageLedger.hospital_id == hospital_id).delete()
    # Delete staff accounts linked to this hospital
    db.query(User).filter(User.hospital_id == hospital_id).delete()
    # Doctors are cascade-deleted via the Hospital relationship,
    # but deleting explicitly here is safer for raw SQL DBs.
    db.query(Doctor).filter(Doctor.hospital_id == hospital_id).delete()

    db.delete(hospital)
    db.commit()

    return {"status": "success", "message": f"Hospital '{hospital.name}' deleted."}