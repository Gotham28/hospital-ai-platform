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


# Meta welcome API is additive; the legacy Twilio contracts above remain intact.
from typing import Literal
from uuid import UUID
from pydantic import StrictBool, ConfigDict
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from app.api.deps import get_token_payload
from app.services.meta_whatsapp import (
    WelcomeError, welcome_config, send_welcome, get_message,
)


class SafeWelcomeRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def safe(request):
            try:
                return await original(request)
            except RequestValidationError:
                # Pydantic normally echoes input values, which may contain patient numbers.
                raise HTTPException(status_code=422, detail={"code": "invalid_request"}) from None
        return safe


welcome_router = APIRouter(route_class=SafeWelcomeRoute)


class SendWelcomeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    phone: str
    language: Literal["en", "ml"]
    consent_confirmed: StrictBool
    request_id: UUID


def _welcome_tenant(hospital_id, payload):
    if payload.get("hospital_id") != hospital_id or not payload.get("sub"):
        raise HTTPException(status_code=403, detail={"code": "not_authorized"})


def _welcome_error(error):
    raise HTTPException(status_code=error.status, detail={"code": error.code}) from None


@welcome_router.get("/welcome-config")
def get_welcome_config(hospital_id: int, db: Session = Depends(get_db), payload: dict = Depends(get_token_payload)):
    _welcome_tenant(hospital_id, payload)
    try:
        return welcome_config(db, hospital_id)
    except WelcomeError as error:
        _welcome_error(error)


@welcome_router.post("/send-welcome")
def post_welcome(hospital_id: int, request: SendWelcomeRequest, db: Session = Depends(get_db), payload: dict = Depends(get_token_payload)):
    _welcome_tenant(hospital_id, payload)
    try:
        return send_welcome(
            db, hospital_id, request.phone, request.language, request.consent_confirmed,
            request.request_id, payload["sub"],
        )
    except WelcomeError as error:
        _welcome_error(error)


@welcome_router.get("/messages/{message_id}")
def welcome_status(hospital_id: int, message_id: int, db: Session = Depends(get_db), payload: dict = Depends(get_token_payload)):
    _welcome_tenant(hospital_id, payload)
    try:
        return get_message(db, hospital_id, message_id)
    except WelcomeError as error:
        _welcome_error(error)


router.include_router(welcome_router)
