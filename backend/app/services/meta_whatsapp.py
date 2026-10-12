"""Meta-only welcome messages. Never persist recipient or provider payload text."""
import hashlib
import hmac
import json
import re
from datetime import datetime, timezone, timedelta
from urllib.parse import quote, urlsplit

import httpx
import phonenumbers
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.core.config import settings
from app.models.hospital import Hospital
from app.models.whatsapp_log import WhatsAppLog


class WelcomeError(Exception):
    def __init__(self, code, status=400):
        self.code = code
        self.status = status
        super().__init__(code)


def normalize_phone(value):
    if not isinstance(value, str) or len(value) > 40 or not re.fullmatch(r"[+0-9 ()-]+", value.strip()):
        raise WelcomeError("invalid_phone")
    try:
        number = phonenumbers.parse(value.strip(), "IN")
        if not phonenumbers.is_valid_number(number):
            raise ValueError()
        if number.country_code == 91 and phonenumbers.number_type(number) not in (
            phonenumbers.PhoneNumberType.MOBILE, phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE,
        ):
            raise ValueError()
        return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)
    except (ValueError, phonenumbers.NumberParseException):
        raise WelcomeError("invalid_phone") from None


def _keyed_hash(value, config):
    return hmac.new(config.WHATSAPP_RECIPIENT_HASH_SECRET.encode(), value.encode(), hashlib.sha256).hexdigest()


def _hospital(db, hospital_id):
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id, Hospital.is_active.is_(True)).first()
    if not hospital:
        raise WelcomeError("hospital_unavailable", 404)
    return hospital


def _template(language, config):
    if language not in ("en", "ml"):
        raise WelcomeError("invalid_language")
    suffix = language.upper()
    name = getattr(config, "META_WHATSAPP_TEMPLATE_" + suffix)
    body = getattr(config, "META_WHATSAPP_TEMPLATE_BODY_" + suffix)
    code = getattr(config, "META_WHATSAPP_LANGUAGE_" + suffix)
    if not re.fullmatch(r"[a-z0-9_]{1,512}", name) or not re.fullmatch(r"[a-z]{2}(?:_[A-Z]{2})?", code):
        raise WelcomeError("setup_required", 503)
    if not body or len(body) > 1024 or set(re.findall(r"\{\{([^{}]+)\}\}", body)) != {"1", "2"}:
        raise WelcomeError("setup_required", 503)
    return name, body, code


def welcome_config(db, hospital_id, config=settings):
    hospital = _hospital(db, hospital_id)
    if not config.META_WHATSAPP_ENABLED:
        return {"enabled": False, "reason": "setup_required", "templates": {}}
    required = (
        config.META_WHATSAPP_ACCESS_TOKEN, config.META_WHATSAPP_APP_SECRET,
        config.META_WHATSAPP_VERIFY_TOKEN,
    )
    if not all(required) or len(config.WHATSAPP_RECIPIENT_HASH_SECRET) < 32:
        raise WelcomeError("setup_required", 503)
    if not re.fullmatch(r"\d+", config.META_WHATSAPP_PHONE_NUMBER_ID) or not re.fullmatch(r"v\d+\.0", config.META_WHATSAPP_GRAPH_VERSION):
        raise WelcomeError("setup_required", 503)
    origin = urlsplit(config.PUBLIC_PATIENT_BASE_URL)
    if origin.scheme != "https" or not origin.hostname or origin.username or origin.password or origin.query or origin.fragment or origin.path not in ("", "/"):
        raise WelcomeError("setup_required", 503)
    allowed = {slug.strip() for slug in config.META_WHATSAPP_ENABLED_HOSPITAL_SLUGS.split(",") if slug.strip()}
    if hospital.slug not in allowed:
        raise WelcomeError("hospital_not_enabled", 503)
    url = config.PUBLIC_PATIENT_BASE_URL.rstrip("/") + "/p/" + quote(hospital.slug, safe="")
    templates = {}
    for language in ("en", "ml"):
        name, body, code = _template(language, config)
        templates[language] = {
            "name": name, "language_code": code,
            "preview": body.replace("{{1}}", hospital.name).replace("{{2}}", url),
        }
    return {"enabled": True, "hospital_name": hospital.name, "assistant_url": url, "templates": templates}


def message_result(row):
    return {
        "message_id": row.id, "masked_phone": row.masked_phone, "status": row.status,
        "language": row.language, "error_code": row.error_code,
    }


def get_message(db, hospital_id, message_id):
    row = db.query(WhatsAppLog).filter(
        WhatsAppLog.id == message_id, WhatsAppLog.hospital_id == hospital_id, WhatsAppLog.provider == "meta",
    ).first()
    if not row:
        raise WelcomeError("message_not_found", 404)
    return message_result(row)


def _post_meta(url, payload, config):
    # No redirects or transport retries: a timed-out POST may have sent successfully.
    with httpx.Client(timeout=10.0, follow_redirects=False) as client:
        return client.post(url, headers={"Authorization": "Bearer " + config.META_WHATSAPP_ACCESS_TOKEN}, json=payload)


def send_welcome(db, hospital_id, phone, language, consent_confirmed, request_id, actor, config=settings):
    if consent_confirmed is not True:
        raise WelcomeError("permission_required")
    phone = normalize_phone(phone)
    if language not in ("en", "ml"):
        raise WelcomeError("invalid_language")
    if len(config.WHATSAPP_RECIPIENT_HASH_SECRET) < 32:
        raise WelcomeError("setup_required", 503)
    # Replay compares original client intent, independent of mutable send setup.
    fingerprint = _keyed_hash(json.dumps([phone, language, True]), config)
    query = db.query(WhatsAppLog).filter(WhatsAppLog.hospital_id == hospital_id, WhatsAppLog.request_id == str(request_id))
    existing = query.first()
    if existing:
        if existing.request_fingerprint != fingerprint:
            raise WelcomeError("request_conflict", 409)
        return message_result(existing)
    info = welcome_config(db, hospital_id, config)
    if not info["enabled"]:
        raise WelcomeError("setup_required", 503)
    template = info["templates"][language]
    values = [info["hospital_name"], info["assistant_url"]]
    now = datetime.now(timezone.utc)
    row = WhatsAppLog(
        hospital_id=hospital_id, masked_phone="*" * (len(phone) - 4) + phone[-4:], status="pending",
        provider="meta", request_id=str(request_id), request_fingerprint=fingerprint, language=language,
        consent_confirmed_at=now, consent_recorded_by=_keyed_hash(str(actor), config), status_updated_at=now,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = query.first()
        if not existing or existing.request_fingerprint != fingerprint:
            raise WelcomeError("request_conflict", 409) from None
        return message_result(existing)
    except SQLAlchemyError:
        db.rollback()
        raise WelcomeError("storage_unavailable", 503) from None
    db.refresh(row)
    payload = {
        "messaging_product": "whatsapp", "to": phone.lstrip("+"), "type": "template",
        "template": {
            "name": template["name"], "language": {"code": template["language_code"]},
            "components": [{"type": "body", "parameters": [{"type": "text", "text": v} for v in values]}],
        },
    }
    row.status, row.error_code = "unknown", "submission_unknown"
    try:
        response = _post_meta(
            "https://graph.facebook.com/" + config.META_WHATSAPP_GRAPH_VERSION + "/" + config.META_WHATSAPP_PHONE_NUMBER_ID + "/messages",
            payload, config,
        )
        # Only a documented successful message ID counts as accepted. Never retain raw responses.
        if 200 <= response.status_code < 300:
            data = response.json()
            message_id = data.get("messages", [{}])[0].get("id")
            if isinstance(message_id, str) and 0 < len(message_id) <= 255:
                row.provider_message_id = message_id
                row.status, row.error_code = "accepted", None
        elif 400 <= response.status_code < 500:
            row.status, row.error_code = "failed", "provider_rejected"
            try:
                error = response.json().get("error", {}).get("code")
                if isinstance(error, int) and not isinstance(error, bool):
                    row.error_code = "meta_" + str(error)[:16]
            except (ValueError, AttributeError, TypeError):
                pass
        # 5xx / unexpected replies stay unknown: no automatic second POST.
    except (httpx.HTTPError, ValueError, TypeError, KeyError, IndexError, AttributeError):
        pass
    row.status_updated_at = datetime.now(timezone.utc)
    try:
        db.commit()
        db.refresh(row)
    except SQLAlchemyError:
        db.rollback()
        # A message may be in flight; preserve the request key and avoid claiming failure.
        raise WelcomeError("submission_unknown", 503) from None
    return message_result(row)


def apply_statuses(db, payload, config=settings):
    if not isinstance(payload, dict) or payload.get("object") != "whatsapp_business_account":
        raise WelcomeError("invalid_callback")
    if not isinstance(payload.get("entry"), list):
        raise WelcomeError("invalid_callback")
    updates = []
    for entry in payload["entry"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("changes"), list):
            raise WelcomeError("invalid_callback")
        for change in entry["changes"]:
            if not isinstance(change, dict):
                raise WelcomeError("invalid_callback")
            if change.get("field") != "messages":
                continue
            value = change.get("value")
            if not isinstance(value, dict):
                raise WelcomeError("invalid_callback")
            metadata = value.get("metadata", {})
            if not isinstance(metadata, dict) or metadata.get("phone_number_id") != config.META_WHATSAPP_PHONE_NUMBER_ID:
                raise WelcomeError("sender_mismatch", 403)
            statuses = value.get("statuses", [])
            if not isinstance(statuses, list):
                raise WelcomeError("invalid_callback")
            for event in statuses:
                if not isinstance(event, dict):
                    raise WelcomeError("invalid_callback")
                if event.get("status") not in ("sent", "delivered", "read", "failed"):
                    continue
                message_id = event.get("id")
                if not isinstance(message_id, str) or len(message_id) > 255:
                    raise WelcomeError("invalid_callback")
                try:
                    timestamp = datetime.fromtimestamp(int(event["timestamp"]), timezone.utc)
                except (KeyError, ValueError, TypeError, OverflowError, OSError):
                    raise WelcomeError("invalid_callback") from None
                row = db.query(WhatsAppLog).filter(
                    WhatsAppLog.provider == "meta", WhatsAppLog.provider_message_id == message_id,
                ).with_for_update().first()
                if not row:
                    recent_pending = db.query(WhatsAppLog.id).filter(
                        WhatsAppLog.provider == "meta", WhatsAppLog.provider_message_id.is_(None),
                        WhatsAppLog.status.in_(["pending", "unknown"]),
                        WhatsAppLog.created_at >= datetime.now(timezone.utc) - timedelta(minutes=5),
                    ).first()
                    if recent_pending:
                        db.rollback()
                        raise WelcomeError("callback_pending", 503)
                    continue  # Other traffic on the shared sender; never trust recipient_id.
                updates.append((row, event["status"], timestamp))
    ranks = {"pending": 0, "unknown": 0, "accepted": 1, "sent": 2, "delivered": 3, "read": 4}
    for row, status, timestamp in updates:
        previous = row.provider_event_at
        if previous and previous.tzinfo is None:
            previous = previous.replace(tzinfo=timezone.utc)
        # A repeated state can carry newer ordering evidence without changing that state.
        if status == row.status:
            if previous is None or timestamp > previous:
                row.provider_event_at = timestamp
                row.status_updated_at = datetime.now(timezone.utc)
            continue
        # Delivery evidence outranks failure; late sent/failed events cannot undo a delivery.
        if status == "failed":
            if row.status in ("delivered", "read", "failed"):
                continue
            if row.status == "sent" and previous and timestamp < previous:
                continue
            row.status, row.error_code = "failed", "delivery_failed"
        else:
            if row.status == "failed" and status == "sent":
                continue
            if ranks.get(status, 0) <= ranks.get(row.status, 0):
                continue
            row.status, row.error_code = status, None
        row.provider_event_at = max(timestamp, previous) if previous else timestamp
        row.status_updated_at = datetime.now(timezone.utc)
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise WelcomeError("storage_unavailable", 503) from None
