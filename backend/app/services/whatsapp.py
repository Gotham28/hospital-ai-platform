import logging
from sqlalchemy.orm import Session
from twilio.rest import Client
from app.models.whatsapp_log import WhatsAppLog
from app.core.config import settings

logger = logging.getLogger(__name__)

TWILIO_ACCOUNT_SID = settings.TWILIO_ACCOUNT_SID
TWILIO_AUTH_TOKEN = settings.TWILIO_AUTH_TOKEN
TWILIO_WHATSAPP_NUMBER = settings.TWILIO_WHATSAPP_NUMBER

client = None
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

def _mask_phone(phone: str) -> str:
    """Masks all but the last 4 digits of a phone number."""
    if not phone or len(phone) <= 4:
        return "****"
    return "*" * (len(phone) - 4) + phone[-4:]

def send_whatsapp_message(db: Session, hospital_id: int, to_number: str, body: str) -> WhatsAppLog:
    if not client:
        logger.warning("[WhatsApp] Twilio credentials not configured.")
        log_entry = WhatsAppLog(
            hospital_id=hospital_id,
            masked_phone=_mask_phone(to_number),
            status="failed",
            error_message="Twilio credentials missing",
        )
        db.add(log_entry)
        db.commit()
        db.refresh(log_entry)
        return log_entry
        
    try:
        # Twilio WhatsApp numbers must be prefixed with 'whatsapp:'
        # Ensure number has + prefix if not present, but assume frontend/API handles basic formatting.
        if not to_number.startswith('+'):
            to_number = f"+{to_number}"
            
        from_phone = f"whatsapp:{TWILIO_WHATSAPP_NUMBER}"
        to_phone = f"whatsapp:{to_number}"
        
        message = client.messages.create(
            body=body,
            from_=from_phone,
            to=to_phone
        )
        
        log_entry = WhatsAppLog(
            hospital_id=hospital_id,
            masked_phone=_mask_phone(to_number),
            status="sent",
            twilio_sid=message.sid
        )
        db.add(log_entry)
        db.commit()
        db.refresh(log_entry)
        logger.info(f"[WhatsApp] Sent message to {_mask_phone(to_number)}, SID: {message.sid}")
        return log_entry
        
    except Exception as e:
        logger.error(f"[WhatsApp] Failed to send message to {_mask_phone(to_number)}: {e}")
        log_entry = WhatsAppLog(
            hospital_id=hospital_id,
            masked_phone=_mask_phone(to_number),
            status="failed",
            error_message=str(e)
        )
        db.add(log_entry)
        db.commit()
        db.refresh(log_entry)
        return log_entry
