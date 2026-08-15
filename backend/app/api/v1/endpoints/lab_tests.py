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
    _tenant: int = Depends(get_current_tenant),
    token_data: dict = Depends(get_token_payload)
):
    db_item = db.query(LabTest).filter(LabTest.id == test_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Lab test not found")

    user_role = token_data.get("role")
    user_hospital = token_data.get("hospital_id")
    if user_role != "superadmin" and str(user_hospital) != str(db_item.hospital_id):
        raise HTTPException(status_code=403, detail="Not authorized to modify this resource")
    
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
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    if token_data.get("role") != "superadmin" and str(token_data.get("hospital_id")) != str(hospital_id):
        raise HTTPException(status_code=403, detail="Access denied")

    content = await file.read()
    text_content = content.decode("utf-8")
    
    reader = csv.DictReader(io.StringIO(text_content))
    csv_headers = reader.fieldnames
    if not csv_headers:
        raise HTTPException(status_code=400, detail="CSV file is empty or invalid.")

    import os
    import json
    from openai import OpenAI
    oai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    target_schema = {
        "name": "Name of the lab test or diagnostic (Required)",
        "category": "Category (e.g., Blood Test, Imaging)",
        "price": "Cost or price of the test",
        "prerequisites": "Preparation instructions (e.g., Fasting required)",
        "turnaround_time": "How long results take to arrive",
        "is_inhouse": "Is this done in the hospital? (Yes/No/Boolean)"
    }

    prompt = f"""
    You are a data mapping assistant. Map these provided CSV headers: {csv_headers}
    To this target database schema: {json.dumps(target_schema)}
    
    Return ONLY a raw JSON object where keys are the database schema keys, and values are the EXACT matching string from the CSV headers.
    If there is no logical match for a target key, set its value to null.
    """

    llm_resp = oai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": prompt}],
        response_format={"type": "json_object"}
    )
    mapping = json.loads(llm_resp.choices[0].message.content)

    count = 0
    for row in reader:
        name_col = mapping.get("name")
        if not name_col or not row.get(name_col):
            continue

        inhouse_col = mapping.get("is_inhouse")
        inhouse_str = str(row.get(inhouse_col, "yes")).lower() if inhouse_col else "yes"
        is_inhouse = inhouse_str in ["yes", "true", "1", "y", "in-house", "inhouse"]

        price_col = mapping.get("price")
        try:
            # Change this line in both files:
            price = float(str(row.get(price_col, 0)).replace("₹", "").replace("$", "").replace(",", "").strip()) if price_col else 0.0
        except ValueError:
            price = 0.0

        cat_col = mapping.get("category")
        prereq_col = mapping.get("prerequisites")
        tat_col = mapping.get("turnaround_time")

        test = LabTest(
            hospital_id=hospital_id,
            name=row.get(name_col).strip(),
            category=row.get(cat_col, "").strip() if cat_col else "",
            price=price,
            prerequisites=row.get(prereq_col, "").strip() if prereq_col else "",
            turnaround_time=row.get(tat_col, "").strip() if tat_col else "",
            is_inhouse=is_inhouse
        )
        db.add(test)
        count += 1

    try:
        db.commit()
        return {"message": f"AI mapping complete. Successfully imported {count} lab tests."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")
@router.patch("/{test_id}", response_model=LabTestSchema)
def update_lab_test(
    test_id: int, 
    payload: LabTestUpdate,
    db: Session = Depends(get_db),
    _tenant: int = Depends(get_current_tenant),
    token_data: dict = Depends(get_token_payload)
):
    db_item = db.query(LabTest).filter(LabTest.id == test_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Lab test not found")

    user_role = token_data.get("role")
    user_hospital = token_data.get("hospital_id")
    if user_role != "superadmin" and str(user_hospital) != str(db_item.hospital_id):
        raise HTTPException(status_code=403, detail="Not authorized to modify this resource")
    
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_item, key, value)
        
    db.commit()
    db.refresh(db_item)
    return db_item