"""Public provider callbacks; verify authenticity before parsing, never log payloads."""
import hashlib
import hmac
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.services.meta_whatsapp import WelcomeError, apply_statuses

router = APIRouter()
MAX_CALLBACK_BYTES = 1_048_576


@router.get("/webhook")
def verify_callback(
    mode: str = Query("", alias="hub.mode"),
    token: str = Query("", alias="hub.verify_token"),
    challenge: str = Query("", alias="hub.challenge"),
):
    if not settings.META_WHATSAPP_VERIFY_TOKEN:
        raise HTTPException(status_code=503, detail={"code": "setup_required"})
    if mode != "subscribe" or not challenge or not hmac.compare_digest(token.encode(), settings.META_WHATSAPP_VERIFY_TOKEN.encode()):
        raise HTTPException(status_code=403, detail={"code": "invalid_verification"})
    return Response(content=challenge, media_type="text/plain")


@router.post("/webhook")
async def receive_callback(request: Request, db: Session = Depends(get_db)):
    if not settings.META_WHATSAPP_APP_SECRET or not settings.META_WHATSAPP_PHONE_NUMBER_ID:
        raise HTTPException(status_code=503, detail={"code": "setup_required"})
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > MAX_CALLBACK_BYTES:
            raise HTTPException(status_code=413, detail={"code": "callback_too_large"})
        raw.extend(chunk)
    signature = request.headers.get("X-Hub-Signature-256", "")
    expected = "sha256=" + hmac.new(settings.META_WHATSAPP_APP_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature.encode(), expected.encode()):
        raise HTTPException(status_code=403, detail={"code": "invalid_signature"})
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail={"code": "invalid_callback"}) from None
    try:
        apply_statuses(db, payload)
    except WelcomeError as error:
        raise HTTPException(status_code=error.status, detail={"code": error.code}) from None
    return {"status": "ok"}
