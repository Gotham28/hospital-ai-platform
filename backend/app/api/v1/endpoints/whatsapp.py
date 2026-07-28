from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel
import openpyxl
from io import BytesIO

from app.api.deps import get_db, get_current_tenant
from app.services.whatsapp import send_whatsapp_message
from app.models.hospital import Hospital

router = APIRouter()

class SendSingleRequest(BaseModel):
    phone: str
    message: str

@router.post("/send-single")
def send_single(
    hospital_id: int,
    request: SendSingleRequest,
    db: Session = Depends(get_db),
    current_tenant_id: int = Depends(get_current_tenant)
):
    if hospital_id != current_tenant_id:
        raise HTTPException(status_code=403, detail="Not authorized for this hospital")
        
    log_entry = send_whatsapp_message(db, hospital_id, request.phone, request.message)
    if log_entry.status == "failed":
        raise HTTPException(status_code=400, detail=log_entry.error_message)
    return {"status": "success", "message": "Message sent", "twilio_sid": log_entry.twilio_sid}

@router.post("/send-bulk")
async def send_bulk(
    hospital_id: int,
    message_template: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_tenant_id: int = Depends(get_current_tenant)
):
    if hospital_id != current_tenant_id:
        raise HTTPException(status_code=403, detail="Not authorized for this hospital")
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Must be an Excel file")
        
    content = await file.read()
    try:
        wb = openpyxl.load_workbook(filename=BytesIO(content), data_only=True)
        sheet = wb.active
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse Excel file: {e}")
        
    rows = list(sheet.iter_rows(values_only=True))
    if not rows or len(rows) < 2:
        raise HTTPException(status_code=400, detail="Excel file is empty or missing data rows")
        
    headers = [str(h).strip() for h in rows[0] if h]
    headers_lower = [h.lower() for h in headers]
    
    if "phone" not in headers_lower:
        raise HTTPException(status_code=400, detail="Excel file must contain a 'Phone' column")
        
    phone_idx = headers_lower.index("phone")
    results = {"sent": 0, "failed": 0, "errors": []}
    
    for idx, row in enumerate(rows[1:], start=2):
        if not row or len(row) <= phone_idx:
            continue
            
        phone = str(row[phone_idx]).strip() if row[phone_idx] else None
        if not phone or phone.lower() == 'none':
            continue
            
        variables = {headers[i]: str(row[i]).strip() if i < len(row) and row[i] is not None else "" for i in range(len(headers))}
        
        body = message_template
        for key, val in variables.items():
            # simple replacement
            body = body.replace(f"{{{key}}}", val)
            
        log_entry = send_whatsapp_message(db, hospital_id, phone, body)
        if log_entry.status == "sent":
            results["sent"] += 1
        else:
            results["failed"] += 1
            results["errors"].append(f"Row {idx} ({log_entry.masked_phone}): {log_entry.error_message}")
            
    return results
