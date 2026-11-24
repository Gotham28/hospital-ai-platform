from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api.deps import get_db, get_token_payload
from app.core.config import settings
from app.services.whatsapp_batch import approve_batch, get_batch
from app.services.whatsapp_import import MAX_BYTES, MAX_ROWS, extract_recipients
from app.services.meta_whatsapp import (
    WelcomeError,
    get_message,
    send_welcome,
    welcome_config,
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


router = APIRouter(route_class=SafeWelcomeRoute)


class SendWelcomeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    phone: str
    language: Literal["en", "ml"]
    consent_confirmed: StrictBool
    request_id: UUID


class ReviewedRecipient(BaseModel):
    model_config = ConfigDict(extra="forbid")
    phone: str = Field(max_length=40)
    language: Literal["en", "ml"]
    reviewed: StrictBool
    consent_confirmed: StrictBool


class ApproveBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recipients: list[ReviewedRecipient] = Field(min_length=1, max_length=MAX_ROWS)


def _welcome_tenant(hospital_id, payload):
    if not payload.get("sub"):
        raise HTTPException(status_code=403, detail={"code": "not_authorized"})
    # The platform superadmin may act for any hospital; the service still scopes every lookup by hospital_id.
    if payload.get("role") == "superadmin":
        return
    if payload.get("hospital_id") != hospital_id:
        raise HTTPException(status_code=403, detail={"code": "not_authorized"})


def _welcome_error(error):
    raise HTTPException(status_code=error.status, detail={"code": error.code}) from None


@router.get("/welcome-config")
def get_welcome_config(hospital_id: int, db: Session = Depends(get_db), payload: dict = Depends(get_token_payload)):
    _welcome_tenant(hospital_id, payload)
    try:
        return {**welcome_config(db, hospital_id), "batch_enabled": settings.META_WHATSAPP_BATCH_ENABLED}
    except WelcomeError as error:
        _welcome_error(error)


@router.post("/welcome-import/{kind}")
async def import_welcome_recipients(
    hospital_id: int, kind: Literal["xlsx", "csv", "pdf", "png", "jpeg"],
    request: Request, payload: dict = Depends(get_token_payload),
):
    _welcome_tenant(hospital_id, payload)
    if not settings.META_WHATSAPP_BATCH_ENABLED:
        raise HTTPException(status_code=503, detail={"code": "batch_setup_required"})
    chunks = bytearray()
    async for part in request.stream():
        if len(chunks) + len(part) > MAX_BYTES:
            raise HTTPException(status_code=413, detail={"code": "file_too_large"})
        chunks.extend(part)
    try:
        rows = await run_in_threadpool(extract_recipients, bytes(chunks), kind)
        return JSONResponse({"rows": rows}, headers={"Cache-Control": "no-store"})
    except WelcomeError as error:
        _welcome_error(error)


@router.post("/welcome-batches/{batch_id}")
def post_welcome_batch(
    hospital_id: int, batch_id: UUID, request: ApproveBatchRequest,
    db: Session = Depends(get_db), payload: dict = Depends(get_token_payload),
):
    _welcome_tenant(hospital_id, payload)
    try:
        return approve_batch(db, hospital_id, batch_id, payload["sub"], request.recipients)
    except WelcomeError as error:
        _welcome_error(error)


@router.get("/welcome-batches/{batch_id}")
def get_welcome_batch(
    hospital_id: int, batch_id: UUID, db: Session = Depends(get_db), payload: dict = Depends(get_token_payload),
):
    _welcome_tenant(hospital_id, payload)
    try:
        return get_batch(db, hospital_id, batch_id, payload["sub"])
    except WelcomeError as error:
        _welcome_error(error)


@router.post("/send-welcome")
def post_welcome(hospital_id: int, request: SendWelcomeRequest, db: Session = Depends(get_db), payload: dict = Depends(get_token_payload)):
    _welcome_tenant(hospital_id, payload)
    try:
        return send_welcome(
            db, hospital_id, request.phone, request.language, request.consent_confirmed,
            request.request_id, payload["sub"],
        )
    except WelcomeError as error:
        _welcome_error(error)


@router.get("/messages/{message_id}")
def welcome_status(hospital_id: int, message_id: int, db: Session = Depends(get_db), payload: dict = Depends(get_token_payload)):
    _welcome_tenant(hospital_id, payload)
    try:
        return get_message(db, hospital_id, message_id)
    except WelcomeError as error:
        _welcome_error(error)
