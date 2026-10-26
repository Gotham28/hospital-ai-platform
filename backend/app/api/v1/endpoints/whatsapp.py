from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, StrictBool
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_token_payload
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


def _welcome_tenant(hospital_id, payload):
    if payload.get("hospital_id") != hospital_id or not payload.get("sub"):
        raise HTTPException(status_code=403, detail={"code": "not_authorized"})


def _welcome_error(error):
    raise HTTPException(status_code=error.status, detail={"code": error.code}) from None


@router.get("/welcome-config")
def get_welcome_config(hospital_id: int, db: Session = Depends(get_db), payload: dict = Depends(get_token_payload)):
    _welcome_tenant(hospital_id, payload)
    try:
        return welcome_config(db, hospital_id)
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
