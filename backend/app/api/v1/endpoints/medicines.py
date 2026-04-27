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

    content = await file.read()
    text_content = content.decode("utf-8")
    
    # 1. Extract just the headers from the CSV
    reader = csv.DictReader(io.StringIO(text_content))
    csv_headers = reader.fieldnames
    if not csv_headers:
        raise HTTPException(status_code=400, detail="CSV file is empty or invalid.")

    # 2. Ask the LLM to map the headers
    import os
    import json
    from openai import OpenAI
    oai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    target_schema = {
        "name": "Generic name or main title of the medicine (Required)",
        "brand_name": "Brand name of the medicine",
        "category": "Type or category (e.g., Tablet, Syrup)",
        "price": "Cost or price of the medicine",
        "stock_status": "Stock availability (e.g., In Stock, Out of Stock)",
        "requires_prescription": "Does it need a prescription? (Yes/No/Boolean)"
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

    # 3. Parse the CSV using the LLM's dynamic mapping
    count = 0
    for row in reader:
        # Get the actual column names from the mapping
        name_col = mapping.get("name")
        if not name_col or not row.get(name_col):
            continue # Skip rows without a primary name

        # Safely parse prescription boolean
        rx_col = mapping.get("requires_prescription")
        req_rx_str = str(row.get(rx_col, "no")).lower() if rx_col else "no"
        requires_prescription = req_rx_str in ["yes", "true", "1", "y", "required"]

        # Safely parse price
        price_col = mapping.get("price")
        try:
# Change this line in both files:
            price = float(str(row.get(price_col, 0)).replace("₹", "").replace("$", "").replace(",", "").strip()) if price_col else 0.0        
        except ValueError:
            price = 0.0

        brand_col = mapping.get("brand_name")
        cat_col = mapping.get("category")
        stock_col = mapping.get("stock_status")

        med = Medicine(
            hospital_id=hospital_id,
            name=row.get(name_col).strip(),
            brand_name=row.get(brand_col, "").strip() if brand_col else "",
            category=row.get(cat_col, "").strip() if cat_col else "",
            price=price,
            stock_status=row.get(stock_col, "in_stock").strip().lower().replace(" ", "_") if stock_col else "in_stock",
            requires_prescription=requires_prescription
        )
        db.add(med)
        count += 1

    try:
        db.commit()
        return {"message": f"AI mapping complete. Successfully imported {count} medicines."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")
    @router.patch("/{medicine_id}", response_model=MedicineSchema)
def update_medicine(
    medicine_id: int, 
    payload: MedicineUpdate,
    db: Session = Depends(get_db),
    _tenant: int = Depends(get_current_tenant)
):
    db_item = db.query(Medicine).filter(Medicine.id == medicine_id).first()
    if not db_item:
        raise HTTPException(status_code=404, detail="Medicine not found")
    
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_item, key, value)
        
    db.commit()
    db.refresh(db_item)
    return db_item