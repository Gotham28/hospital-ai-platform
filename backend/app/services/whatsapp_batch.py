"""Persist approved recipients until the worker submits them or their queue entries expire."""
import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta, timezone
from uuid import NAMESPACE_URL, uuid4, uuid5

from apscheduler.schedulers.background import BackgroundScheduler
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import and_, or_

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.hospital import Hospital
from app.models.whatsapp_batch import WhatsAppBatchItem as Item
from app.models.whatsapp_log import WhatsAppLog
from app.services.meta_whatsapp import WelcomeError, normalize_phone, send_welcome, welcome_config

_scheduler = BackgroundScheduler()
_logger = logging.getLogger(__name__)
_QUEUE_TTL = timedelta(hours=1)
_LEASE = timedelta(minutes=2)


def _now():
    return datetime.now(timezone.utc)


def _hash(*parts):
    message = json.dumps(parts, separators=(",", ":")).encode()
    return hmac.new(settings.WHATSAPP_RECIPIENT_HASH_SECRET.encode(), message, hashlib.sha256).hexdigest()


def _cipher():
    try:
        return Fernet(settings.WHATSAPP_BATCH_ENCRYPTION_KEY.encode())
    except (ValueError, TypeError):
        raise WelcomeError("batch_setup_required", 503) from None


def _require_batch():
    if not settings.META_WHATSAPP_BATCH_ENABLED or len(settings.WHATSAPP_RECIPIENT_HASH_SECRET) < 32:
        raise WelcomeError("batch_setup_required", 503)
    return _cipher()


def _items(db, hospital_id, batch_id):
    return db.query(Item).filter(Item.hospital_id == hospital_id, Item.batch_id == str(batch_id))


def _status(db, items):
    message_ids = [item.message_id for item in items if item.message_id is not None]
    logs = {}
    if message_ids:
        logs = {row.id: row for row in db.query(WhatsAppLog).filter(
            WhatsAppLog.hospital_id == items[0].hospital_id,
            WhatsAppLog.provider == "meta",
            WhatsAppLog.id.in_(message_ids),
        )}
    return {"batch_id": items[0].batch_id, "items": [
        {
            "position": item.position,
            "masked_phone": item.masked_phone,
            "status": _reported_status(item, logs.get(item.message_id)),
            "error_code": logs[item.message_id].error_code if item.message_id in logs else None,
        }
        for item in items
    ]}


def _reported_status(item, log):
    if log is None or (item.status == "unknown" and log.status == "pending"):
        return item.status
    return log.status


def get_batch(db, hospital_id, batch_id, actor):
    items = _items(db, hospital_id, batch_id).filter(
        Item.actor_hash == _hash("batch actor", hospital_id, actor),
    ).order_by(Item.position).all()
    if not items:
        raise WelcomeError("batch_not_found", 404)
    return _status(db, items)


def approve_batch(db, hospital_id, batch_id, actor, recipients):
    cipher = _require_batch()
    phones = [normalize_phone(row.phone) for row in recipients]
    if len(set(phones)) != len(phones):
        raise WelcomeError("duplicate_recipients")
    if any(not row.reviewed or not row.consent_confirmed for row in recipients):
        raise WelcomeError("permission_required")
    actor_hash = _hash("batch actor", hospital_id, actor)
    approval_hash = _hash("batch approval", list(zip(phones, (row.language for row in recipients))))
    # Serialize approvals within each hospital, including from different staff accounts.
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id, Hospital.is_active.is_(True)).with_for_update().first()
    if not hospital:
        raise WelcomeError("hospital_unavailable", 404)
    existing = _items(db, hospital_id, batch_id).order_by(Item.position).all()
    if existing:
        if existing[0].actor_hash != actor_hash or existing[0].approval_hash != approval_hash:
            raise WelcomeError("request_conflict", 409)
        return _status(db, existing)
    if not welcome_config(db, hospital_id)["enabled"]:
        raise WelcomeError("setup_required", 503)

    recipient_hashes = [_hash("batch recipient", hospital_id, phone) for phone in phones]
    blocking = db.query(Item.id).outerjoin(WhatsAppLog, and_(
        WhatsAppLog.id == Item.message_id, WhatsAppLog.hospital_id == Item.hospital_id,
    )).filter(
        Item.hospital_id == hospital_id,
        Item.recipient_hash.in_(recipient_hashes),
        or_(
            Item.status.in_(("queued", "processing")),
            and_(Item.status == "unknown", Item.message_id.is_(None)),
            WhatsAppLog.status.in_(("pending", "unknown")),
        ),
    ).first()
    if blocking:
        raise WelcomeError("recipient_already_in_progress", 409)

    now = _now()
    items = [
        Item(
            hospital_id=hospital_id, batch_id=str(batch_id), position=index,
            actor_hash=actor_hash, approval_hash=approval_hash, recipient_hash=recipient_hash,
            encrypted_phone=cipher.encrypt(phone.encode()), masked_phone="*" * (len(phone) - 4) + phone[-4:],
            language=recipient.language, status="queued", available_at=now, expires_at=now + _QUEUE_TTL,
        )
        for index, (recipient, phone, recipient_hash) in enumerate(zip(recipients, phones, recipient_hashes))
    ]
    db.add_all(items)
    result = _status(db, items)
    db.commit()
    return result


def _process_one():
    now = _now()
    with SessionLocal() as db:
        # Expired approvals cannot authorize a new provider request.
        for status, final in (("queued", "expired"), ("processing", "unknown")):
            db.query(Item).filter(
                Item.status == status, Item.expires_at <= now, Item.available_at <= now,
            ).update({Item.status: final, Item.encrypted_phone: None, Item.claim_id: None})
        db.commit()
        if not settings.META_WHATSAPP_ENABLED or not settings.META_WHATSAPP_BATCH_ENABLED:
            return
        cipher = _cipher()
        item = db.query(Item).filter(
            Item.status.in_(("queued", "processing")),
            Item.available_at <= now, Item.expires_at > now,
        ).order_by(Item.available_at, Item.id).with_for_update(skip_locked=True).first()
        if not item:
            return
        claim = str(uuid4())
        item_id, hospital_id = item.id, item.hospital_id
        phone_blob, language, actor = item.encrypted_phone, item.language, item.actor_hash
        request_id = uuid5(NAMESPACE_URL, f"arogya:whatsapp:batch:{hospital_id}:{item.batch_id}:{item.position}")
        item.status, item.available_at, item.claim_id = "processing", now + _LEASE, claim
        db.commit()
        message_id = None
        try:
            phone = cipher.decrypt(phone_blob).decode()
        except (InvalidToken, TypeError, UnicodeError):
            status = "unknown"
        else:
            try:
                result = send_welcome(db, hospital_id, phone, language, True, request_id, actor)
                status = "unknown" if result["status"] == "pending" else result["status"]
                message_id = result["message_id"]
            except WelcomeError as error:
                status = "unknown" if error.code in ("submission_unknown", "request_conflict") else "failed"
                db.rollback()
                if status == "unknown":
                    message = db.query(WhatsAppLog).filter(
                        WhatsAppLog.hospital_id == hospital_id, WhatsAppLog.provider == "meta",
                        WhatsAppLog.request_id == str(request_id),
                    ).first()
                    if message:
                        message_id = message.id

        db.query(Item).filter(Item.id == item_id, Item.hospital_id == hospital_id, Item.claim_id == claim).update({
            Item.status: status, Item.encrypted_phone: None, Item.message_id: message_id, Item.claim_id: None,
        })
        db.commit()


def _tick():
    try:
        _process_one()
    except Exception:
        # Database errors may include query parameters. Keep worker logs free of recipient data.
        _logger.error("WhatsApp batch worker could not process the queue")


def start_whatsapp_batch_worker():
    configured = settings.META_WHATSAPP_BATCH_ENABLED or bool(settings.WHATSAPP_BATCH_ENCRYPTION_KEY)
    if configured and not _scheduler.running:
        _scheduler.add_job(_tick, "interval", seconds=3, max_instances=1, coalesce=True)
        _scheduler.start()


def stop_whatsapp_batch_worker():
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
