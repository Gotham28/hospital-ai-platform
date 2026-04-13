import os
import re
import json
import fitz
import logging
import unicodedata
import httpx
from typing import List, Optional, AsyncGenerator
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator
from openai import OpenAI, AsyncOpenAI
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.api.deps import get_db
from app.models.hospital import Hospital
from app.models.knowledge import KnowledgeBase
from app.models.usage import UsageLedger
from app.models.doctor import Doctor
from app.availability import (
    get_doctor_availability,
    get_cached_or_empty,
    AvailabilityError,
)
import redis
import uuid
from app.models.appointment import Appointment
logger = logging.getLogger(__name__)
router = APIRouter()

_api_key = os.getenv("OPENAI_API_KEY")
if not _api_key:
    raise RuntimeError("OPENAI_API_KEY environment variable is not set.")

client = OpenAI(api_key=_api_key)
async_client = AsyncOpenAI(api_key=_api_key)
_redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
_redis = redis.from_url(_redis_url, decode_responses=True)
BOOKING_SESSION_TTL = 600

MAX_HISTORY_TURNS        = 10
PDF_CHUNK_SIZE           = 800
PDF_CHUNK_OVERLAP        = 100
DOCTOR_SECTION_MAX_CHARS = 2_400
KB_CHUNK_MAX_CHARS       = 500
KB_SECTION_MAX_CHARS     = 1_500
MAX_RELEVANT_DOCTORS     = 15
DEFAULT_DOCTORS_IF_NO_MATCH = 5
SYSTEM_PROMPT_WARN_CHARS = 12_000
QUESTION_MIN_LENGTH      = 1
QUESTION_MAX_LENGTH      = 500
VALID_LANGUAGES          = {"en", "ml"}


# =============================================================================
# GOOGLE TRANSLATE BRIDGE
# =============================================================================

_GTRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"

def _translate(text: str, source: str, target: str) -> str:
    if not text or not text.strip():
        return text
    try:
        params = {"client": "gtx", "sl": source, "tl": target, "dt": "t", "q": text}
        resp = httpx.get(_GTRANSLATE_URL, params=params, timeout=8.0)
        resp.raise_for_status()
        data = resp.json()
        return "".join(part[0] for part in data[0] if part[0])
    except Exception as e:
        logger.warning("Translation failed (%s->%s): %s", source, target, e)
        return text


async def _translate_async(text: str, source: str, target: str) -> str:
    if not text or not text.strip():
        return text
    try:
        params = {"client": "gtx", "sl": source, "tl": target, "dt": "t", "q": text}
        async with httpx.AsyncClient() as http:
            resp = await http.get(_GTRANSLATE_URL, params=params, timeout=8.0)
            resp.raise_for_status()
            data = resp.json()
            return "".join(part[0] for part in data[0] if part[0])
    except Exception as e:
        logger.warning("Async translation failed (%s->%s): %s", source, target, e)
        return text

# =============================================================================
# BOOKING SESSION STATE MACHINE
# paste this block into ai.py, right after the GOOGLE TRANSLATE BRIDGE section
# and before the INJECTION DETECTION section
# =============================================================================

# --- Add to imports at top of ai.py ---
# import redis
# import uuid
# from app.models.appointment import Appointment  (add to existing model imports)

# --- Redis client setup (add near client = OpenAI(...)) ---
# _redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
# _redis = redis.from_url(_redis_url, decode_responses=True)
# BOOKING_SESSION_TTL = 600  # 10 minutes — session expires if user goes idle

# =============================================================================
# Booking intent keywords (English — question is already translated before here)
# =============================================================================
_BOOKING_KEYWORDS = [
    "book", "appointment", "schedule", "consult", "consultation",
    "see a doctor", "visit", "reserve", "fix an appointment",
    "make an appointment", "set appointment",
]

def detect_booking_intent(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in _BOOKING_KEYWORDS)


# =============================================================================
# Session helpers
# =============================================================================

def _session_key(hospital_id: str, session_token: str) -> str:
    return f"booking:{hospital_id}:{session_token}"


def get_booking_session(hospital_id: str, session_token: str) -> dict | None:
    raw = _redis.get(_session_key(hospital_id, session_token))
    if not raw:
        return None
    import json as _json
    return _json.loads(raw)


def save_booking_session(hospital_id: str, session_token: str, session: dict) -> None:
    import json as _json
    _redis.setex(
        _session_key(hospital_id, session_token),
        BOOKING_SESSION_TTL,
        _json.dumps(session)
    )


def clear_booking_session(hospital_id: str, session_token: str) -> None:
    _redis.delete(_session_key(hospital_id, session_token))


def new_booking_session() -> dict:
    return {
        "state": "collecting_doctor",
        "doctor_id": None,
        "doctor_name": None,
        "preferred_date": None,
        "time_of_day": None,
        "patient_name": None,
        "patient_age": None,
        "patient_phone": None,
    }


# =============================================================================
# State machine — one function per state, returns the bot reply and next state
# =============================================================================

def _booking_step(
    user_message: str,
    session: dict,
    hospital_id: int,
    language: str,
    db,          # SQLAlchemy Session
) -> tuple[str, dict, bool]:
    """
    Process one turn of the booking conversation.

    Returns:
        bot_reply   — what the bot should say (in English; translated upstream)
        session     — updated session dict
        done        — True if booking is complete or cancelled
    """
    from app.models.doctor import Doctor
    from app.models.hospital import Hospital
    from app.models.appointment import Appointment
    from app.services.booking_rules import validate_booking, get_booking_config
    from app.services.email import notify_staff_new_appointment
    import uuid, re
    from datetime import datetime, timedelta

    msg = user_message.strip()
    msg_lower = msg.lower() # Pre-compute lowercase for fuzzy matching
    state = session["state"]

    # Global cancel check (Fuzzy match)
    if any(w in msg_lower for w in ["cancel", "stop", "nevermind", "never mind", "quit", "exit"]):
        return "Okay, I've cancelled the appointment booking. Is there anything else I can help you with?", session, True

    # ── State: collecting_doctor ──────────────────────────────────────────────
    if state == "collecting_doctor":
        all_doctors = db.query(Doctor).filter(Doctor.hospital_id == hospital_id).all()
        if not all_doctors:
            return "I'm sorry, there are no doctors registered for online booking at this time. Please call reception.", session, True

        # Try to match the user's text to a doctor name or department
        from app.api.v1.endpoints.ai import score_doctor_relevance  # reuse existing function
        scored = sorted(
            [(score_doctor_relevance(msg, d), d) for d in all_doctors],
            key=lambda x: x[0], reverse=True
        )
        best_score, best_doc = scored[0] if scored else (0, None)

        if best_score >= 0.3 and best_doc:
            session["doctor_id"]   = best_doc.id
            session["doctor_name"] = best_doc.name
            session["state"]       = "collecting_date"

            # Build date options: next 7 days excluding today
            today = datetime.now()
            date_options = []
            for i in range(1, 8):
                d = today + timedelta(days=i)
                date_options.append(d.strftime("%A, %B %d (%Y-%m-%d)"))

            dates_text = "\n".join(f"  {i+1}. {d}" for i, d in enumerate(date_options))
            return (
                f"Great! I'll book you with **{best_doc.name}** ({best_doc.department}).\n\n"
                f"Which date would you prefer? Please choose:\n{dates_text}\n\n"
                "You can type the number or the date."
            ), session, False
        else:
            # Show doctor list for them to choose
            doctor_list = "\n".join(
                f"  {i+1}. Dr. {d.name} — {d.department or 'General'}"
                for i, (_, d) in enumerate(scored[:8])
            )
            return (
                f"Which doctor would you like to book an appointment with?\n\n{doctor_list}\n\n"
                "You can type the doctor's name, department, or number."
            ), session, False

    # ── State: collecting_date ────────────────────────────────────────────────
    if state == "collecting_date":
        today = datetime.now()
        date_options = [(today + timedelta(days=i)) for i in range(1, 8)]

        chosen_date = None

        # Try number choice (Fuzzy match: strips out periods or text added by translator like "Option 1.")
        digits_only = re.sub(r"[^\d]", "", msg)
        if digits_only:
            idx = int(digits_only) - 1
            if 0 <= idx < len(date_options):
                chosen_date = date_options[idx].strftime("%Y-%m-%d")

        # Try direct date parsing
        if not chosen_date:
            for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%B %d", "%b %d"):
                try:
                    parsed = datetime.strptime(msg, fmt)
                    if parsed.year == 1900:
                        parsed = parsed.replace(year=today.year)
                    chosen_date = parsed.strftime("%Y-%m-%d")
                    break
                except ValueError:
                    continue

        # Try day name ("monday", "tuesday" etc)
        if not chosen_date:
            day_names = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]
            for dn in day_names:
                if dn in msg_lower:
                    for d in date_options:
                        if d.strftime("%A").lower() == dn:
                            chosen_date = d.strftime("%Y-%m-%d")
                            break

        if not chosen_date:
            date_list = "\n".join(f"  {i+1}. {d.strftime('%A, %B %d')}" for i, d in enumerate(date_options))
            return (
                "I didn't catch that date. Please choose a number from the list:\n"
                f"{date_list}"
            ), session, False

        session["preferred_date"] = chosen_date
        session["state"] = "collecting_time_of_day"
        return (
            f"Got it — **{chosen_date}**.\n\n"
            "What time of day works best for you?\n"
            "  1. 🌅 Morning\n"
            "  2. ☀️ Afternoon\n"
            "  3. 🌇 Evening"
        ), session, False

    # ── State: collecting_time_of_day ─────────────────────────────────────────
    if state == "collecting_time_of_day":
        # FIX: Fuzzy keyword matching instead of exact dictionary lookup
        if any(w in msg_lower for w in ["1", "morning", "am", "early"]):
            tod = "morning"
        elif any(w in msg_lower for w in ["2", "afternoon", "noon", "midday"]):
            tod = "afternoon"
        elif any(w in msg_lower for w in ["3", "evening", "pm", "night", "late"]):
            tod = "evening"
        else:
            return (
                "Please choose:\n  1. Morning\n  2. Afternoon\n  3. Evening"
            ), session, False

        session["time_of_day"] = tod
        session["state"] = "collecting_name"
        return "What is the patient's full name?", session, False

    # ── State: collecting_name ────────────────────────────────────────────────
    if state == "collecting_name":
        if len(msg) < 2:
            return "Please enter a valid full name.", session, False
        
        # Extract name only — stop at conjunctions the translation layer adds
        # e.g. "Reetha and she is 50 years old" → "Reetha"
        name_part = re.split(
            r'\b(and|she|he|is|was|who|aged|age|years?|her|his|the)\b',
            msg, flags=re.IGNORECASE
        )[0]
        name_clean = name_part.strip("., ").title()
        
        if len(name_clean) < 2:
            return "Please enter a valid full name.", session, False
        
        # Check if the message also contains an age — if so, auto-capture it
        age_match = re.search(r'\b(\d{1,3})\s*(years?(\s*old)?|yr)?\b', msg, re.IGNORECASE)
        
        session["patient_name"] = name_clean
        
        if age_match:
            age_val = int(age_match.group(1))
            if 1 <= age_val <= 120:
                session["patient_age"] = str(age_val)
                session["state"] = "collecting_phone"
                return (
                    f"Got it — **{name_clean}**, age **{age_val}**. "
                    "What is the best phone number to reach the patient?"
                ), session, False
        
        session["state"] = "collecting_age"
        return f"Thank you, {session['patient_name']}. What is the patient's age?", session, False

    # ── State: collecting_age ─────────────────────────────────────────────────
    if state == "collecting_age":
        age = re.sub(r"[^\d]", "", msg)
        if not age or not (1 <= int(age) <= 120):
            return "Please enter a valid age (e.g. 32).", session, False
        session["patient_age"] = age
        session["state"] = "collecting_phone"
        return "What is the best phone number to reach the patient?", session, False

    # ── State: collecting_phone ───────────────────────────────────────────────
    
    if state == "collecting_phone":
        phone = re.sub(r"[\s\-\(\)\.]", "", msg)
        # Indian numbers: 10 digits, optionally prefixed with +91 or 0
        # General international: 7-15 digits
        phone_digits = re.sub(r"^\+91|^91|^0", "", phone)  # strip country code for length check
        if not re.match(r"^\+?\d{7,15}$", phone):
            return "Please enter a valid phone number (e.g. 9876543210).", session, False
        if len(phone_digits) not in (10, 11, 12) and not phone.startswith("+"):
            return (
                f"That number has {len(phone_digits)} digits — Indian mobile numbers should have 10 digits. "
                "Please check and re-enter."
            ), session, False
        session["patient_phone"] = phone
        session["state"] = "confirming"

        # Build confirmation summary
        return (
            f"Please confirm your appointment request:\n\n"
            f"👨‍⚕️ **Doctor:** {session['doctor_name']}\n"
            f"📅 **Date:** {session['preferred_date']}\n"
            f"🕐 **Time:** {session['time_of_day'].title()}\n"
            f"👤 **Patient:** {session['patient_name']}\n"
            f"🎂 **Age:** {session['patient_age']}\n"
            f"📞 **Phone:** {session['patient_phone']}\n\n"
            "Type **yes** to confirm or **no** to cancel."
        ), session, False

    # ── State: confirming ─────────────────────────────────────────────────────
    if state == "confirming":
        correction_map = {
        "phone": "collecting_phone",
        "number": "collecting_phone",
        "mobile": "collecting_phone",
        "name": "collecting_name",
        "age": "collecting_age",
        "date": "collecting_date",
        "time": "collecting_time_of_day",
        "doctor": "collecting_doctor",
    }
        for keyword, go_to_state in correction_map.items():
            if f"change {keyword}" in msg_lower or f"wrong {keyword}" in msg_lower or f"edit {keyword}" in msg_lower or f"correct {keyword}" in msg_lower:
                session["state"] = go_to_state
                prompts = {
                "collecting_phone": "Please enter the correct phone number.",
                "collecting_name": "Please enter the correct patient name.",
                "collecting_age": "Please enter the correct age.",
                "collecting_date": "Please enter the correct date.",
                "collecting_time_of_day": "Please choose the time: 1. Morning  2. Afternoon  3. Evening",
                "collecting_doctor": "Which doctor would you like instead?",
            }
            return prompts[go_to_state], session, False
        # FIX: Fuzzy keyword matching for confirmation
        positive_words = ["yes", "confirm", "ok", "okay", "sure", "proceed", "y", "correct", "right", "exactly", "do it"]
        negative_words = ["no", "cancel", "n", "stop", "incorrect", "wrong", "wait"]

        if any(w in msg_lower for w in positive_words):
            # Write to database
            hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
            doctor   = db.query(Doctor).filter(Doctor.id == session["doctor_id"]).first()

            # Validate booking rules one final time
            from app.services.booking_rules import validate_booking, get_booking_config
            ok, error = validate_booking(hospital, doctor, session["preferred_date"], db)
            if not ok:
                return error, session, True

            appt = Appointment(
                hospital_id=hospital_id,
                doctor_id=session["doctor_id"],
                patient_name=session["patient_name"],
                patient_age=session["patient_age"],
                patient_phone=session["patient_phone"],
                preferred_date=session["preferred_date"],
                time_of_day=session["time_of_day"],
                status="pending",
            )
            db.add(appt)
            db.commit()
            db.refresh(appt)

            # Fire staff email
            config = get_booking_config(hospital)
            staff_email = config.get("notification_email", "")
            if staff_email:
                notify_staff_new_appointment(
                    staff_email=staff_email,
                    hospital_name=hospital.name,
                    reference=appt.reference_number,
                    patient_name=appt.patient_name,
                    patient_age=appt.patient_age,
                    patient_phone=appt.patient_phone,
                    doctor_name=doctor.name,
                    preferred_date=appt.preferred_date,
                    time_of_day=appt.time_of_day,
                )

            return (
                f"✅ **Appointment Request Submitted!**\n\n"
                f"Your reference number is: **{appt.reference_number}**\n\n"
                f"The hospital will call you at **{appt.patient_phone}** to confirm your slot. "
                f"You can also ask me 'what is my appointment status' at any time to check.\n\n"
                f"Is there anything else I can help you with?"
            ), session, True

        elif any(w in msg_lower for w in negative_words):
            return "Booking cancelled. Is there anything else I can help you with?", session, True
        else:
            return "Please type **yes** to confirm or **no** to cancel.", session, False

    return "Something went wrong. Please try again.", session, True
# =============================================================================
# INJECTION DETECTION
# =============================================================================

_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above|your)\s+(instructions?|prompt|rules?|guidelines?)", re.IGNORECASE),
    re.compile(r"(disregard|forget|override|bypass|circumvent)\s+(your\s+)?(instructions?|guidelines?|rules?|prompt|training)", re.IGNORECASE),
    re.compile(r"(your\s+new|new\s+instructions?\s+(are|is)|from\s+now\s+on\s+you)", re.IGNORECASE),
    re.compile(r"\byou\s+are\s+now\b", re.IGNORECASE),
    re.compile(r"\b(act|behave|pretend|roleplay|role-play|simulate)\s+(as|like)\b", re.IGNORECASE),
    re.compile(r"\b(DAN|jailbreak|do\s+anything\s+now)\b", re.IGNORECASE),
    re.compile(r"(^|\s)(system|assistant)\s*:", re.IGNORECASE | re.MULTILINE),
    re.compile(r"(\[INST\]|<<SYS>>|<</SYS>>|\[/INST\])", re.IGNORECASE),
    re.compile(r"(repeat|show|print|reveal|display|tell me|what (are|is))\s+(your\s+)?(system\s+)?(prompt|instructions?|guidelines?|rules?)", re.IGNORECASE),
]

def detect_prompt_injection(text: str) -> Optional[str]:
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            return "Prompt injection detected."
    return None


# =============================================================================
# REQUEST / RESPONSE MODELS
# =============================================================================

class HistoryMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    question: str
    hospital_id: int
    language: str = Field(default="en")
    history: Optional[List[HistoryMessage]] = None
    session_token: str = Field(default="default")  # ← add this line


    @field_validator("language")
    @classmethod
    def language_valid(cls, v: str) -> str:
        if v not in VALID_LANGUAGES:
            raise ValueError(f"language must be one of {sorted(VALID_LANGUAGES)}")
        return v

    @field_validator("question")
    @classmethod
    def question_valid(cls, v: str) -> str:
        v = unicodedata.normalize("NFKC", v).strip()
        if len(v) < QUESTION_MIN_LENGTH:
            raise ValueError("Question too short.")
        if len(v) > QUESTION_MAX_LENGTH:
            raise ValueError(f"Question exceeds {QUESTION_MAX_LENGTH} characters.")
        injection = detect_prompt_injection(v)
        if injection:
            raise ValueError(injection)
        return v

class IngestRequest(BaseModel):
    hospital_id: int
    text: str


# =============================================================================
# DOCTOR RELEVANCE FILTERING
# =============================================================================

# Synonym map — variants for common department name spellings/abbreviations.
# Both directions are listed so matching works regardless of which side uses
# which spelling.
_DEPT_SYNONYMS: dict[str, list[str]] = {
    "orthopaedics":     ["orthopedics", "ortho", "orthopedic", "orthopaedic", "bone", "joint"],
    "orthopedics":      ["orthopaedics", "ortho", "orthopedic", "orthopaedic", "bone", "joint"],
    "cardiology":       ["cardiac", "heart", "cardio"],
    "general medicine": ["general", "medicine", "physician", "gm"],
    "gynaecology":      ["gynecology", "gynae", "obstetrics", "obgyn", "ob-gyn", "women"],
    "gynecology":       ["gynaecology", "gynae", "obstetrics", "obgyn", "ob-gyn", "women"],
    "paediatrics":      ["pediatrics", "paediatric", "pediatric", "child", "children"],
    "pediatrics":       ["paediatrics", "paediatric", "pediatric", "child", "children"],
    "dermatology":      ["derma", "skin"],
    "neurology":        ["neuro", "brain", "nerve"],
    "ophthalmology":    ["eye", "ophthal", "vision"],
    "ent":              ["ear", "nose", "throat", "otolaryngology"],
    "psychiatry":       ["mental health", "psychology", "psych"],
    "oncology":         ["cancer", "tumor", "tumour"],
    "urology":          ["urological", "kidney", "bladder"],
    "nephrology":       ["kidney", "renal"],
    "pulmonology":      ["lung", "chest", "respiratory", "pulmonary"],
    "gastroenterology": ["gastro", "digestive", "stomach", "gut", "gi"],
    "endocrinology":    ["diabetes", "thyroid", "hormones", "endocrine"],
    "rheumatology":     ["arthritis", "rheumatic", "joints"],
    "surgery":          ["surgical", "general surgery", "laparoscopy", "laproscopy"],
    "dentistry":        ["dental", "teeth", "tooth"],
    "physiotherapy":    ["physio", "rehabilitation", "rehab"],
    "radiology":        ["xray", "x-ray", "imaging", "scan", "mri"],
    "anesthesiology":   ["anaesthesia", "anesthesia", "anaesthesiology"],
}

def _expand_with_synonyms(tokens: set) -> set:
    """Expand a token set with department synonyms."""
    expanded = set(tokens)
    for token in tokens:
        for canonical, variants in _DEPT_SYNONYMS.items():
            if token == canonical or token in variants:
                expanded.add(canonical)
                expanded.update(variants)
    return expanded


def normalize_name(text: str) -> str:
    """Lowercase, strip Dr. prefix, keep only latin letters and spaces."""
    text = text.lower()
    text = re.sub(r"dr\.?\s*", "", text)
    text = re.sub(r"[^a-z\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def score_doctor_relevance(question: str, doctor: Doctor) -> float:
    """
    Score how relevant a doctor entry is to the (English) question.

    Uses synonym expansion so spelling variants ("orthopedics" vs
    "orthopaedics") and abbreviations ("ortho") all match correctly.
    A substring fallback handles partial department names.
    """
    q_norm = normalize_name(question)
    q_tokens = set(q_norm.split())
    if not q_tokens:
        return 0.0

    dept  = normalize_name(doctor.department or "")
    name  = normalize_name(doctor.name or "")
    # Support both field names used across different versions of the model
    sched = normalize_name(
        getattr(doctor, "base_schedule", None)
        or getattr(doctor, "schedule", None)
        or ""
    )

    d_tokens = set((dept + " " + name + " " + sched).split())
    if not d_tokens:
        return 0.0

    q_expanded = _expand_with_synonyms(q_tokens)
    d_expanded = _expand_with_synonyms(d_tokens)

    token_score = len(q_expanded & d_expanded) / len(q_expanded)

    # Substring fallback: "ortho" in "orthopaedics"
    substring_score = 0.0
    for qt in q_tokens:
        if len(qt) >= 4 and qt in dept:
            substring_score = max(substring_score, 0.6)

    return max(token_score, substring_score)


def build_doctor_context(question: str, doctors: list) -> tuple[str, int]:
    if not doctors:
        return "No doctors currently registered for this hospital.\n", 0

    scored = sorted(
        [(score_doctor_relevance(question, d), d) for d in doctors],
        key=lambda x: x[0], reverse=True
    )
    top_score = scored[0][0] if scored else 0.0
    limit = MAX_RELEVANT_DOCTORS if top_score > 0.05 else DEFAULT_DOCTORS_IF_NO_MATCH

    lines, total_chars, truncated = [], 0, False
    for _, doctor in scored[:limit]:
        schedule = (
            getattr(doctor, "base_schedule", None)
            or getattr(doctor, "schedule", None)
            or "Not specified"
        )
        line = f"- {doctor.name} ({doctor.department or 'General'}): Schedule {schedule}\n"
        if total_chars + len(line) > DOCTOR_SECTION_MAX_CHARS:
            truncated = True
            break
        lines.append(line)
        total_chars += len(line)

    section = "RELEVANT DOCTORS FOR THIS QUERY:\n" + "".join(lines)
    if truncated:
        section += f"(List truncated. Total doctors on file: {len(doctors)})\n"
    return section, len(lines)


def resolve_doctor_id(user_text: str, doctor_data: dict):
    nq = normalize_name(user_text)
    best_match, best_score = None, 0
    for did, d in doctor_data.items():
        name = d.get("name", "") if isinstance(d, dict) else str(d)
        nn = normalize_name(name)
        qt, nt = set(nq.split()), set(nn.split())
        if not qt or not nt:
            continue
        score = len(qt & nt) / len(nt)
        if score > best_score:
            best_score = score
            best_match = (did, name)
    return best_match if best_score >= 0.5 else (None, None)


# =============================================================================
# KB CONTEXT
# =============================================================================

def build_kb_context(results: list) -> tuple[str, int]:
    if not results:
        return "", 0
    trimmed, total = [], 0
    for row in results:
        text = (row.content or "").strip()
        if not text:
            continue
        if len(text) > KB_CHUNK_MAX_CHARS:
            text = text[:KB_CHUNK_MAX_CHARS].rsplit(" ", 1)[0] + "..."
        if total + len(text) > KB_SECTION_MAX_CHARS:
            break
        trimmed.append(text)
        total += len(text)
    return ("\n---\n".join(trimmed), len(trimmed)) if trimmed else ("", 0)


# =============================================================================
# AVAILABILITY
# =============================================================================

def fetch_availability_context(question: str, sheet_id: str, hospital_id: int, today_str: str) -> str:
    try:
        data = get_doctor_availability(sheet_id=sheet_id)
        doc_id, doc_name = resolve_doctor_id(question, data)
        if not doc_id:
            return ""
        doc_info = data.get(doc_id, {})
        absent = [d.strip() for d in str(doc_info.get("absent_dates", "")).split(",") if d.strip()]
        if today_str in absent:
            return (f"IMPORTANT LIVE STATUS: {doc_name} is ABSENT TODAY ({today_str}). "
                    "Tell the patient they are unavailable and suggest calling reception.")
        return f"LIVE STATUS: {doc_name} is available today ({today_str})."
    except Exception as e:
        logger.exception("[Availability] Unexpected error hospital_id=%s: %s", hospital_id, e)
        return ""


# =============================================================================
# SYSTEM PROMPT BUILDER
# =============================================================================

def build_system_prompt_english() -> str:
    return "Respond in English only. Be clear, accurate, and concise."


def build_fallback_instruction() -> str:
    return """IMPORTANT - WHEN YOU DO NOT KNOW SOMETHING:
If the patient asks about something not mentioned in the doctor list or knowledge
above (e.g. pharmacy location, visiting hours, room numbers, fees) and you do not
have that information:
- Say clearly: "I don't have that information. Please ask at the reception desk."

Do NOT make up answers. Do NOT say information that is not in your context above."""


def build_context(request: ChatRequest, db: Session, force_english: bool = False):
    hospital_id = request.hospital_id
    question = request.question
    today_str = datetime.now().strftime("%d-%m-%Y")

    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    all_doctors = db.query(Doctor).filter(Doctor.hospital_id == hospital_id).all()
    doctor_context, doctors_included = build_doctor_context(question, all_doctors)

    availability_context = ""
    if hospital.google_sheet_id:
        availability_context = fetch_availability_context(question, hospital.google_sheet_id, hospital_id, today_str)

    embed_resp = client.embeddings.create(input=question, model="text-embedding-3-small")
    raw_results = (
        db.query(KnowledgeBase)
        .filter(KnowledgeBase.hospital_id == hospital_id)
        .order_by(KnowledgeBase.embedding.cosine_distance(embed_resp.data[0].embedding))
        .limit(3).all()
    )
    kb_context, chunks_included = build_kb_context(raw_results)

    lang_instruction = build_system_prompt_english()
    fallback_instruction = build_fallback_instruction()

    parts = [
        f"You are Arogya, the AI Assistant for {hospital.name}.",
        f"Current Date: {today_str}",
        "",
        hospital.system_prompt or "",
        "",
        lang_instruction,
        "",
        doctor_context,
    ]

    if availability_context:
        parts.append(availability_context)

    if kb_context:
        parts.extend(["", "ADDITIONAL KNOWLEDGE BASE:", kb_context])

    parts.extend(["", fallback_instruction])

    system_prompt = "\n".join(parts)

    prompt_chars = len(system_prompt)
    if prompt_chars > SYSTEM_PROMPT_WARN_CHARS:
        logger.warning(
            "System prompt over soft limit hospital_id=%s: %d chars (~%d tokens) doctors=%d/%d kb=%d",
            hospital_id, prompt_chars, prompt_chars // 4, doctors_included, len(all_doctors), chunks_included,
        )

    history_messages = build_history_messages(request.history or [])
    openai_messages = (
        [{"role": "system", "content": system_prompt}]
        + history_messages
        + [{"role": "user", "content": question}]
    )
    return system_prompt, openai_messages, hospital


# =============================================================================
# HISTORY
# =============================================================================

def build_history_messages(history: List[HistoryMessage]) -> List[dict]:
    if not history:
        return []
    trimmed = history[-(MAX_HISTORY_TURNS * 2):]
    if trimmed and trimmed[0].role != "user":
        trimmed = trimmed[1:]
    return [{"role": m.role, "content": m.content} for m in trimmed]


# =============================================================================
# PDF HELPERS
# =============================================================================

def extract_text_from_pdf(pdf_bytes: bytes) -> tuple[str, int]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages_text = []
    for i, page in enumerate(doc):
        text = page.get_text("text").strip()
        if text:
            pages_text.append(f"[Page {i + 1}]\n{text}")
    count = len(doc)
    doc.close()
    return "\n\n".join(pages_text), count


def chunk_text(text: str) -> List[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=PDF_CHUNK_SIZE, chunk_overlap=PDF_CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return [c.strip() for c in splitter.split_text(text) if len(c.strip()) > 50]


def embed_chunks_batch(chunks: List[str]) -> List[List[float]]:
    result = []
    for i in range(0, len(chunks), 100):
        resp = client.embeddings.create(input=chunks[i:i+100], model="text-embedding-3-small")
        result.extend([item.embedding for item in resp.data])
    return result


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/welcome/{hospital_id}")
async def get_welcome(hospital_id: int, db: Session = Depends(get_db)):
    """
    Returns a personalised welcome message for the chat UI.
    Lists exactly what this hospital's bot can help with, based on
    what is actually configured (doctors, KB, etc.).

    Response: { "en": "...", "ml": "..." }
    """
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    doctors = db.query(Doctor).filter(Doctor.hospital_id == hospital_id).all()
    has_kb = db.query(KnowledgeBase).filter(KnowledgeBase.hospital_id == hospital_id).first() is not None

    dept_names = sorted({d.department for d in doctors if d.department})

    en_caps, ml_caps = [], []

    if doctors:
        dept_list = ", ".join(dept_names) if dept_names else "General"
        en_caps.append(f"🩺 Tell you about our doctors — {dept_list}")
        ml_caps.append(f"🩺 ഞങ്ങളുടെ ഡോക്ടർമാരെ കുറിച്ച് പറയുക — {dept_list}")
        en_caps.append("📅 Share doctor schedules and today's availability")
        ml_caps.append("📅 ഡോക്ടറുടെ ഷെഡ്യൂളും ഇന്നത്തെ ലഭ്യതയും")

    if has_kb:
        en_caps.append("🏥 Answer questions about the hospital (timings, services, etc.)")
        ml_caps.append("🏥 ആശുപത്രിയെ കുറിച്ചുള്ള ചോദ്യങ്ങൾക്ക് മറുപടി നൽകുക")

    en_caps.append("📞 Guide you to the right department or contact")
    ml_caps.append("📞 ശരിയായ വിഭാഗത്തിലേക്കോ ബന്ധപ്പെടുന്നതിന് നിർദ്ദേശം നൽകുക")

    hospital_name = hospital.name or "this hospital"

    en_msg = "\n".join([
        f"👋 Hello! I am **Arogya**, the AI assistant for **{hospital_name}**.",
        "",
        "Here is what I can help you with:",
        *[f"- {c}" for c in en_caps],
        "",
        "Just type or speak your question! 🎤",
    ])

    ml_msg = "\n".join([
        f"👋 നമസ്കാരം! ഞാൻ **ആരോഗ്യ**, **{hospital_name}**-ന്റെ AI അസിസ്റ്റന്റ്.",
        "",
        "ഞാൻ ഇവ സഹായിക്കാം:",
        *[f"- {c}" for c in ml_caps],
        "",
        "താഴെ ടൈപ്പ് ചെയ്യൂ അല്ലെങ്കിൽ സംസാരിക്കൂ! 🎤",
    ])

    return {"en": en_msg, "ml": ml_msg}


@router.get("/suggestions/{hospital_id}")
async def get_suggestions(hospital_id: int, db: Session = Depends(get_db)):
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    doctors = db.query(Doctor).filter(Doctor.hospital_id == hospital_id).limit(3).all()
    has_kb = db.query(KnowledgeBase).filter(KnowledgeBase.hospital_id == hospital_id).first() is not None

    en_suggestions, ml_suggestions = [], []

    if doctors:
        for doctor in doctors[:2]:
            dept = doctor.department or "General"
            en_suggestions.append(f"Who is the {dept} doctor?")
            ml_suggestions.append(f"{dept} ഡോക്ടർ ആരാണ്?")
        en_suggestions.append("Which doctors are available today?")
        ml_suggestions.append("ഇന്ന് ഏത് ഡോക്ടർ ഉണ്ട്?")
    else:
        en_suggestions.append("What can Arogya help me with?")
        ml_suggestions.append("ആരോഗ്യ എന്തൊക്കെ സഹായിക്കും?")

    if has_kb:
        en_suggestions.append("What are the hospital timings?")
        ml_suggestions.append("ആശുപത്രി സമയം എന്താണ്?")
    else:
        en_suggestions.append("How do I contact the hospital?")
        ml_suggestions.append("ആശുപത്രിയിൽ എങ്ങനെ ബന്ധപ്പെടാം?")

    en_suggestions.append("Tell me about this hospital")
    ml_suggestions.append("ഈ ആശുപത്രിയെക്കുറിച്ച് പറയൂ")

    return {"en": en_suggestions[:4], "ml": ml_suggestions[:4]}


@router.post("/ingest")
async def ingest_knowledge(request: IngestRequest, db: Session = Depends(get_db)):
    try:
        resp = client.embeddings.create(input=request.text, model="text-embedding-3-small")
        db.add(KnowledgeBase(
            hospital_id=request.hospital_id,
            content=request.text,
            embedding=resp.data[0].embedding,
            created_at=datetime.utcnow()
        ))
        db.commit()
        return {"status": "success", "message": "Knowledge added to Arogya's brain"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...), hospital_id: int = Form(...), db: Session = Depends(get_db)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="Only PDF files are accepted.")
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")
    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=422, detail="Empty file.")
    if not pdf_bytes.startswith(b"%PDF"):
        raise HTTPException(status_code=422, detail="Not a valid PDF.")
    try:
        full_text, page_count = extract_text_from_pdf(pdf_bytes)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not read PDF: {e}")
    if not full_text.strip():
        raise HTTPException(status_code=422, detail="No readable text. Scanned PDFs are not supported.")
    chunks = chunk_text(full_text)
    if not chunks:
        raise HTTPException(status_code=422, detail="PDF too short to produce knowledge chunks.")
    try:
        embeddings = embed_chunks_batch(chunks)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding failed: {e}")
    try:
        for content, embedding in zip(chunks, embeddings):
            db.add(KnowledgeBase(hospital_id=hospital_id, content=content, embedding=embedding, created_at=datetime.utcnow()))
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    return {
        "status": "success", "filename": file.filename,
        "pages_processed": page_count, "chunks_stored": len(chunks),
        "total_characters": sum(len(c) for c in chunks),
        "message": f"'{file.filename}' -> {len(chunks)} chunks stored for {hospital.name}."
    }


@router.post("/chat")
async def chat_with_arogya(request: ChatRequest, db: Session = Depends(get_db)):
    is_malayalam = request.language == "ml"

    english_question = request.question
    if is_malayalam:
        english_question = _translate(request.question, source="ml", target="en")
        logger.info("[Translation] ml->en: %r -> %r", request.question[:80], english_question[:80])

    translated_request = request.model_copy(update={"question": english_question})
    _, openai_messages, _ = build_context(translated_request, db, force_english=True)

    ai_response = client.chat.completions.create(model="gpt-4o-mini", messages=openai_messages)
    english_answer = ai_response.choices[0].message.content or ""

    final_answer = english_answer
    if is_malayalam:
        final_answer = _translate(english_answer, source="en", target="ml")

    usage = ai_response.usage
    db.add(UsageLedger(
        hospital_id=request.hospital_id, endpoint="/chat",
        prompt_tokens=usage.prompt_tokens, completion_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens, estimated_cost=(usage.total_tokens / 1_000_000) * 0.15
    ))
    db.commit()
    return {"answer": final_answer}


@router.post("/chat-stream")
async def chat_stream(request: ChatRequest, db: Session = Depends(get_db)):
    is_malayalam = request.language == "ml"

    english_question = request.question
    if is_malayalam:
        english_question = await _translate_async(request.question, source="ml", target="en")
        logger.info("[Translation] ml->en: %r -> %r", request.question[:80], english_question[:80])

    translated_request = request.model_copy(update={"question": english_question})
    _, openai_messages, _ = build_context(translated_request, db, force_english=True)
    # ── Booking session intercept ─────────────────────────────────────────────
    session_token = request.session_token  # add this field to ChatRequest model
    booking_session = get_booking_session(str(request.hospital_id), session_token)

    is_new_booking = not booking_session and detect_booking_intent(english_question)
    if booking_session or is_new_booking:
        if not booking_session:
            booking_session = new_booking_session()
            # Pre-fill doctor from recent conversation history if detectable
            if is_new_booking and request.history:
                all_doctors = db.query(Doctor).filter(
                    Doctor.hospital_id == request.hospital_id
                ).all()
                # Search last 4 messages for a doctor mention
                recent_text = " ".join(
                    m.content for m in (request.history or [])[-4:]
                )
                scored = sorted(
                    [(score_doctor_relevance(recent_text, d), d) for d in all_doctors],
                    key=lambda x: x[0], reverse=True
                )
                if scored and scored[0][0] >= 0.3:
                    best = scored[0][1]
                    booking_session["doctor_id"]   = best.id
                    booking_session["doctor_name"] = best.name
                    booking_session["state"]       = "collecting_date"
                    # Build date list for immediate reply
                    from datetime import timedelta
                    today = datetime.now()
                    date_options = [
                        (today + timedelta(days=i)).strftime("%A, %B %d (%Y-%m-%d)")
                        for i in range(1, 8)
                    ]
                    dates_text = "\n".join(f"  {i+1}. {d}" for i, d in enumerate(date_options))
                    pre_reply = (
                        f"Sure! I'll book you with **{best.name}** ({best.department}).\n\n"
                        f"Which date would you prefer?\n{dates_text}\n\n"
                        "You can type the number or the date."
                    )
                    if request.language == "ml":
                        pre_reply = await _translate_async(pre_reply, "en", "ml")
                    save_booking_session(str(request.hospital_id), session_token, booking_session)
                    async def pre_booking_reply():
                        yield f"data: {json.dumps(pre_reply)}\n\n"
                        yield "data: [DONE]\n\n"
                    return StreamingResponse(pre_booking_reply(), media_type="text/event-stream",
                        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
    # ── end booking intercept — normal chat continues below ───────────────────

    async def event_generator() -> AsyncGenerator[str, None]:
        pt = ct = tt = 0
        english_chunks: List[str] = []

        try:
            stream = await async_client.chat.completions.create(
                model="gpt-4o-mini", messages=openai_messages,
                stream=True, stream_options={"include_usage": True}
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                token = delta.content if delta and delta.content else None
                if token:
                    if is_malayalam:
                        english_chunks.append(token)
                    else:
                        yield f"data: {json.dumps(token)}\n\n"
                if chunk.usage:
                    pt, ct, tt = chunk.usage.prompt_tokens, chunk.usage.completion_tokens, chunk.usage.total_tokens

            if is_malayalam and english_chunks:
                full_english = "".join(english_chunks)
                full_malayalam = await _translate_async(full_english, source="en", target="ml")
                sentences = re.split(r'(?<=[.!?।\n])\s*', full_malayalam)
                for sentence in sentences:
                    if sentence.strip():
                        yield f"data: {json.dumps(sentence + ' ')}\n\n"

            yield "data: [DONE]\n\n"

            if tt > 0:
                db.add(UsageLedger(
                    hospital_id=request.hospital_id, endpoint="/chat-stream",
                    prompt_tokens=pt, completion_tokens=ct, total_tokens=tt,
                    estimated_cost=(tt / 1_000_000) * 0.15
                ))
                db.commit()

        except Exception as e:
            logger.exception("[chat-stream] Error: %s", e)
            yield f"data: [ERROR] {str(e)}\n\n"

    return StreamingResponse(
        event_generator(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"}
    )