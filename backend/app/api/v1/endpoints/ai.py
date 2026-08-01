import os
import re
import json
import fitz
import logging
import unicodedata
import httpx
import time              # ← ADD
import uuid
from typing import List, Optional, AsyncGenerator
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field, field_validator, model_validator
from openai import OpenAI, AsyncOpenAI
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from fastapi import APIRouter, UploadFile, File, HTTPException
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.core.config import settings
from app.api.deps import get_db
from app.models.hospital import Hospital
from app.services.security import detect_prompt_injection
from app.services.translation import _translate, _translate_async
from app.models.knowledge import KnowledgeBase
from app.models.usage import UsageLedger
from app.models.doctor import Doctor
from app.models.medicine import Medicine
from app.models.lab_test import LabTest
from app.models.doctor_availability import DoctorSchedule, DoctorLeave
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
BOOKING_SESSION_TTL      = 600
OPENAI_MODEL    = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_MODEL_ML = os.getenv("OPENAI_MODEL_ML", "gpt-4o")
OPENAI_COST_PER_MTok     = float(os.getenv("OPENAI_COST_PER_MTok", "0.15"))
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
# GOOGLE TRANSLATE BRIDGE  (kept only for fallback / STT post-processing)
# =============================================================================
PATIENT_CTX_TTL = 600   # matches BOOKING_SESSION_TTL; both keys expire together
 
 
def _patient_ctx_key(hospital_id: int, session_token: str) -> str:
    """Redis key for patient personalisation (separate from booking state)."""
    return f"patient_ctx:{hospital_id}:{session_token}"
 
 
def _load_patient_ctx(hospital_id: int, session_token: str) -> dict:
    """
    Return the current patient context dict, or {} if none exists yet.
 
    Schema
    ------
    {
      "doctor_id":   int | None,
      "doctor_name": str | None,
      "department":  str | None,      # canonical department string
      "language":    "en" | "ml",
      "seen_topics": list[str]        # e.g. ["pharmacy", "appointment"]
    }
    """
    try:
        raw = _redis.get(_patient_ctx_key(hospital_id, session_token))
        if raw:
            return json.loads(raw)
    except Exception as exc:
        logger.warning("[PatientCtx] load failed: %s", exc)
    return {}
 
 
def _save_patient_ctx(hospital_id: int, session_token: str, ctx: dict) -> None:
    """Write (or refresh TTL of) the patient context in Redis."""
    try:
        _redis.setex(
            _patient_ctx_key(hospital_id, session_token),
            PATIENT_CTX_TTL,
            json.dumps(ctx),
        )
        logger.info("[PatientCtx] saved: %s", json.dumps(ctx))  # ← ADD THIS LINE
    except Exception as exc:
        logger.warning("[PatientCtx] save failed: %s", exc)
 
 
def _update_patient_ctx(
    hospital_id: int,
    session_token: str,
    *,
    language: str,
    question_en: str,
    history: list,
    db,
) -> dict:
    """
    Deterministically update patient context from the current turn.
    No LLM call — purely regex/keyword matching, so it adds < 1 ms.
 
    Call this ONCE per request, outside event_generator(), so the context
    is already updated before streaming begins.
 
    Returns the updated context dict.
    """
    ctx = _load_patient_ctx(hospital_id, session_token)
    is_new_session = not ctx 

    # ── 0. Session timing / turn count (for task-completion metric) ───────
    if "session_started_at" not in ctx:
        ctx["session_started_at"] = time.time()
    ctx["turn_count"] = ctx.get("turn_count", 0) + 1

    # ── 1. Language preference ────────────────────────────────────────────
    ctx["language"] = language   # always authoritative from the live request  # always authoritative from the live request
 
    # ── 2. Doctor / department from the most recent assistant turn ────────
    # The doctor context lines we already inject look like:
    #   "- [ID: 7] Dr. Priya (Cardiology): Available today from ..."
    # Pick up the ID and hydrate name + department from the DB.
    if history:
        for msg in reversed(history):
            if msg.role == "assistant":
                id_match = re.search(r"\[ID:\s*(\d+)\]", msg.content)
                if id_match:
                    doctor_id = int(id_match.group(1))
                    if ctx.get("doctor_id") != doctor_id:
                        try:
                            doc = (
                                db.query(Doctor)
                                .filter(
                                    Doctor.id == doctor_id,
                                    Doctor.hospital_id == hospital_id,  # tenant-scoped
                                )
                                .first()
                            )
                            if doc:
                                ctx["doctor_id"]   = doc.id
                                ctx["doctor_name"] = doc.name
                                ctx["department"]  = doc.department
                        except Exception as exc:
                            logger.warning("[PatientCtx] doctor lookup failed: %s", exc)
                break   # only look at the single most-recent assistant message
 
    # ── 3. Department from the user question (fallback) ───────────────────
    # Uses the existing _DEPT_SYNONYMS dict — no extra work needed.
    if not ctx.get("department"):
        q_lower = question_en.lower()
        for canonical, variants in _DEPT_SYNONYMS.items():
            if canonical in q_lower or any(v in q_lower for v in variants):
                ctx["department"] = canonical
                break
 
    # ── 4. Seen-topics accumulation ───────────────────────────────────────
    seen = set(ctx.get("seen_topics", []))
    topic_keywords: dict[str, list[str]] = {
        "pharmacy":     ["medicine", "pharmacy", "drug", "tablet", "pill"],
        "lab_tests":    ["lab", "test", "blood", "scan", "diagnostic", "x-ray"],
        "appointment":  ["book", "appointment", "schedule", "reserve"],
        "availability": ["available", "availability", "timing", "when", "today"],
    }
    for topic, keywords in topic_keywords.items():
        if any(kw in question_en.lower() for kw in keywords):
            seen.add(topic)
    ctx["seen_topics"] = list(seen)
    ctx["_is_new_session"] = is_new_session
    _save_patient_ctx(hospital_id, session_token, ctx)
    return ctx
 
 
def _build_patient_ctx_block(ctx: dict) -> str:
    """
    Render the patient context as a concise system-prompt block.
    Returns "" when ctx is empty (clean no-op for new sessions).
    """
    if not ctx:
        return ""
 
    lines = ["PATIENT CONTEXT THIS SESSION:"]
 
    if ctx.get("doctor_name"):
        dept_str = f" ({ctx['department']})" if ctx.get("department") else ""
        lines.append(
            f"  • The patient has already discussed Dr. {ctx['doctor_name']}"
            f"{dept_str} [ID: {ctx['doctor_id']}] — reference this doctor"
            f" without re-introducing them."
        )
    elif ctx.get("department"):
        lines.append(
            f"  • The patient is interested in the {ctx['department'].title()} department."
        )
 
    lang_label = {"ml": "Malayalam", "en": "English"}.get(
        ctx.get("language", "en"), "English"
    )
    lines.append(f"  • Preferred language this session: {lang_label}.")
 
    seen = ctx.get("seen_topics", [])
    if seen:
        readable_map = {
            "pharmacy":     "pharmacy / medicines",
            "lab_tests":    "lab tests",
            "appointment":  "appointment booking",
            "availability": "doctor availability",
        }
        readable = [readable_map.get(t, t) for t in seen]
        lines.append(
            f"  • Topics already covered this session: {', '.join(readable)}."
        )
        lines.append(
            "    Do not repeat the same basic information; instead build on it."
        )
 
    lines.append("")   # trailing newline so the block is visually separated
    return "\n".join(lines)
 
def _log_task_completion(hospital_id: int, session_token: str, ctx: dict, outcome: str) -> None:
    """
    Log the task-completion metric for this session: turns and elapsed time
    from first message to a terminal outcome (booking success so far;
    'abandoned' can be logged the same way later if we add session-expiry
    hooks). One structured log line per completed session — grep on
    "[TaskCompletion]" to pull these for analysis, or ship them to whatever
    log aggregation you already have. Deliberately not a new DB table yet;
    the plan only asks that this be logged, not eyeballed.
    """
    started_at = ctx.get("session_started_at")
    turns = ctx.get("turn_count", 0)
    elapsed_seconds = round(time.time() - started_at, 1) if started_at else None
    logger.info(
        "[TaskCompletion] hospital_id=%s session=%s outcome=%s turns=%s elapsed_seconds=%s",
        hospital_id, session_token, outcome, turns, elapsed_seconds,
    )

# =============================================================================
# FEATURE 4 — RELEVANCE GATE HELPERS
# =============================================================================

# Stage sequencing for the multi-turn relevance Q&A
_RELEVANCE_STAGES = ["asked_referral", "asked_prior_docs", "asked_symptom", "done"]


def _reset_relevance_gate(ctx: dict) -> dict:
    """Clear all relevance gate keys. Called when a new booking attempt starts."""
    ctx.pop("relevance_stage",   None)
    ctx.pop("relevance_answers", None)
    ctx.pop("relevance_verdict", None)
    return ctx


def _is_new_booking_attempt(ctx: dict) -> bool:
    """
    Return True if the patient has already completed at least one booking in
    this session AND the relevance gate still holds a cached verdict from that
    prior booking. That combination means we must reset and re-run the gate.
    """
    return (
        ctx.get("booking_completed_at") is not None
        and ctx.get("relevance_stage") == "done"
    )

# TRANSLATION functions moved to app.services.translation


# =============================================================================
# Session helpers
# =============================================================================

# TODO: Confirmed unused via grep on 2026-08-01. Remove in future cleanup task.
# def _session_key(hospital_id: str, session_token: str) -> str:
#     return f"booking:{hospital_id}:{session_token}"


# INJECTION DETECTION moved to app.services.security


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
    session_token: str = Field(default="default")

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
    entry_type: str = "fact"
    @field_validator("entry_type")
    @classmethod
    def entry_type_valid(cls, v: str) -> str:
        if v not in {"fact", "instruction"}:
            raise ValueError("entry_type must be 'fact' or 'instruction'")
        return v



# =============================================================================
# DOCTOR RELEVANCE FILTERING
# =============================================================================

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
    expanded = set(tokens)
    for token in tokens:
        for canonical, variants in _DEPT_SYNONYMS.items():
            if token == canonical or token in variants:
                expanded.add(canonical)
                expanded.update(variants)
    return expanded


def normalize_name(text: str) -> str:
    text = text.lower()
    text = re.sub(r"dr\.?\s*", "", text)
    text = re.sub(r"[^a-z\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def score_doctor_relevance(question: str, doctor: Doctor) -> float:
    q_norm = normalize_name(question)
    q_tokens = set(q_norm.split())
    if not q_tokens:
        return 0.0

    dept  = normalize_name(doctor.department or "")
    name  = normalize_name(doctor.name or "")
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

    substring_score = 0.0
    for qt in q_tokens:
        if len(qt) >= 4 and qt in dept:
            substring_score = max(substring_score, 0.6)

    return max(token_score, substring_score)


def check_doctor_availability_db(doctor: Doctor, db: Session, target_date: datetime) -> str:
    leave = db.query(DoctorLeave).filter(
        DoctorLeave.doctor_id == doctor.id,
        DoctorLeave.date == target_date.date()
    ).first()
    if leave:
        reason = f" ({leave.reason})" if leave.reason else ""
        return f"ABSENT TODAY{reason}"

    day_of_week = target_date.weekday()

    has_any_schedule = db.query(DoctorSchedule).filter(DoctorSchedule.doctor_id == doctor.id).first() is not None

    schedule = db.query(DoctorSchedule).filter(
        DoctorSchedule.doctor_id == doctor.id,
        DoctorSchedule.day_of_week == day_of_week,
        DoctorSchedule.is_active == True
    ).first()

    if schedule:
        return f"Available today from {schedule.start_time} to {schedule.end_time}"

    if has_any_schedule:
        return "Not scheduled to work today"
    else:
        base = getattr(doctor, "base_schedule", None)
        if base and base.lower() != "not specified":
            return f"Standard Timings: {base}"
        return "Timings not specified"


def build_doctor_context(question: str, hospital_id: int, db: Session) -> tuple[str, int]:
    today = datetime.now()

    broad_keywords = {"all", "list", "doctors", "staff", "everyone", "available"}
    is_broad = len(set(question.lower().split()) & broad_keywords) >= 2

    doctors = []
    if not is_broad:
        try:
            q_embedding = client.embeddings.create(
                input=question, model="text-embedding-3-small"
            ).data[0].embedding
            doctors = (
                db.query(Doctor)
                .filter(Doctor.hospital_id == hospital_id)
                .filter(Doctor.embedding != None)
                .order_by(Doctor.embedding.cosine_distance(q_embedding))
                .limit(8)
                .all()
            )
        except Exception as e:
            logger.warning(f"Embedding search failed: {e}")

    if is_broad or len(doctors) < 3:
        doctors = (
            db.query(Doctor)
            .filter(Doctor.hospital_id == hospital_id)
            .limit(30)
            .all()
        )

    if not doctors:
        return "No doctors currently registered for this hospital.\n", 0

    lines = ["RELEVANT DOCTORS AND AVAILABILITY:\n"]
    for doctor in doctors:
        status = check_doctor_availability_db(doctor, db, today)
        lines.append(
            f"- [ID: {doctor.id}] Dr. {doctor.name} "
            f"({doctor.department or 'General'}): {status}\n"
        )
    return "".join(lines), len(doctors)


def build_pharmacy_context(question: str, medicines: list) -> str:
    nq = normalize_name(question)
    q_tokens = set(nq.split())
    if not q_tokens or not medicines:
        return ""

    scored = []
    for m in medicines:
        m_text = normalize_name(f"{m.name} {m.brand_name or ''} {m.category or ''}")
        m_tokens = set(m_text.split())
        score = len(q_tokens & m_tokens)
        if score > 0:
            scored.append((score, m))

    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored:
        return ""

    lines = ["RELEVANT PHARMACY ITEMS:"]
    for _, m in scored[:5]:
        req_rx = "Prescription Required" if m.requires_prescription else "Over-the-counter"
        status = (m.stock_status or "in_stock").replace("_", " ").title()
        lines.append(f"- {m.name} ({m.brand_name or 'Generic'}): Status: {status}, Price: ₹{m.price or 'N/A'}, {req_rx}")

    return "\n".join(lines) + "\n"


def build_lab_tests_context(question: str, tests: list) -> str:
    nq = normalize_name(question)
    q_tokens = set(nq.split())
    if not q_tokens or not tests:
        return ""

    scored = []
    for t in tests:
        t_text = normalize_name(f"{t.name} {t.category or ''}")
        t_tokens = set(t_text.split())
        score = len(q_tokens & t_tokens)
        if score > 0:
            scored.append((score, t))

    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored:
        return ""

    lines = ["RELEVANT LAB TESTS:"]
    for _, t in scored[:5]:
        loc = "In-house" if t.is_inhouse else "External Partner"
        lines.append(f"- {t.name} ({t.category or 'General'}): Price: ₹{t.price or 'N/A'}, Turnaround: {t.turnaround_time or 'N/A'}, Location: {loc}")
        if t.prerequisites:
            lines.append(f"  Preparation/Prerequisites: {t.prerequisites}")
        if getattr(t, "is_outsourced", False) and getattr(t, "outsourced_note", None):
            lines.append(f"  Note: {t.outsourced_note}")

    return "\n".join(lines) + "\n"


# TODO: Confirmed unused via grep on 2026-08-01. Remove in future cleanup task.
# def resolve_doctor_id(user_text: str, doctor_data: dict):
#     nq = normalize_name(user_text)
#     best_match, best_score = None, 0
#     for did, d in doctor_data.items():
#         name = d.get("name", "") if isinstance(d, dict) else str(d)
#         nn = normalize_name(name)
#         qt, nt = set(nq.split()), set(nn.split())
#         if not qt or not nt:
#             continue
#         score = len(qt & nt) / len(nt)
#         if score > best_score:
#             best_score = score
#             best_match = (did, name)
#     return best_match if best_score >= 0.5 else (None, None)


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
# SYSTEM PROMPT BUILDER
# =============================================================================

def build_system_prompt_english() -> str:
    return """You are responding in ENGLISH.
You are Arogya — a warm, cheerful hospital assistant who genuinely loves helping patients.
Be friendly, positive and reassuring. Use a caring tone like a kind receptionist who is happy to help.
Keep answers concise — 1 to 2 short sentences. Never sound robotic or cold.
Always use "Dr." prefix for doctors and speak about them respectfully.
If you can help, say so enthusiastically. If something is outside your knowledge, warmly suggest calling reception.
Treat each question independently — do not carry assumptions from a previous topic."""


def build_system_prompt_malayalam() -> str:
    return """നിങ്ങൾ Arogya ആണ് — രോഗികളെ സഹായിക്കാൻ എപ്പോഴും സന്തോഷത്തോടെ തയ്യാറുള്ള ഒരു ആശുപത്രി സഹായി.
സ്നേഹത്തോടെ, ഊഷ്മളമായി, ഉത്സാഹത്തോടെ മറുപടി നൽകൂ — അടുത്ത വീട്ടുകാരൻ സംസാരിക്കുന്നതുപോലെ.
ചുരുക്കമായി — 1 മുതൽ 2 വാക്യം മാത്രം. സഹായിക്കാൻ കഴിഞ്ഞാൽ സന്തോഷത്തോടെ പറയൂ.

നിയമങ്ങൾ:
- "എല്ലാവിധ", "ഉറപ്പിക്കൂ", "ആദരണീയ" പോലുള്ള formal വാക്കുകൾ ഉപയോഗിക്കരുത്
- ദിവസം കൃത്യമായി പറയുക: ഞായർ തിങ്കൾ ചൊവ്വ ബുധൻ വ്യാഴം വെള്ളി ശനി
- ഡോക്ടർ: "ഡോക്ടർ [പേര്]" എന്ന് വിളിക്കുക. "അദ്ദേഹം" അല്ലെങ്കിൽ "ആ ഡോക്ടർ" എന്ന് ഉപയോഗിക്കുക. "അവൻ", "അവൾ", "ഇവൻ", "ഇവൾ" എന്നിവ ഒരിക്കലും ഉപയോഗിക്കരുത്.
- Medical terms (Cardiology, General Medicine, etc.) ഇംഗ്ലീഷിൽ തന്നെ നിലനിർത്തുക
- ഓരോ ചോദ്യവും സ്വതന്ത്രമായി ഉത്തരം നൽകുക — മുൻ topic carry forward ചെയ്യരുത്"""


def build_fallback_instruction(doctors_found: int, kb_chunks: int, has_pharmacy: bool, has_labs: bool) -> str:
    sources = []
    if doctors_found > 0:
        sources.append(f"{doctors_found} relevant doctors with live availability")
    if kb_chunks > 0:
        sources.append(f"{kb_chunks} hospital knowledge base entries")
    if has_pharmacy:
        sources.append("pharmacy inventory")
    if has_labs:
        sources.append("lab test catalog")

    source_desc = ", ".join(sources) if sources else "no structured data"

    return f"""You have access to: {source_desc}.

Answer confidently from this data. If asked about something genuinely outside this data 
(specific room numbers, exact wait times, billing disputes), acknowledge you don't have 
that specific detail and suggest calling reception. Never refuse to answer about doctors, 
departments, or services that appear in your context above."""


def build_context(
    request: "ChatRequest",
    db: "Session",
    force_english: bool = False,
    session_token: str = "default",   # ← NEW: carries the session's Redis key
):
    hospital_id = request.hospital_id
    question    = request.question
    prompt_date_str = datetime.now().strftime("%A, %B %d, %Y")
 
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")
 
    # Defence-in-depth: assert tenant isolation before building any context.
    assert hospital.id == hospital_id, (
        f"Cross-tenant leak: requested {hospital_id}, got {hospital.id}"
    )
 
    all_medicines = db.query(Medicine).filter(Medicine.hospital_id == hospital_id).all()
    all_tests     = db.query(LabTest).filter(LabTest.hospital_id == hospital_id).all()
 
    doctor_context, doctors_included = build_doctor_context(question, hospital_id, db)
    pharmacy_context  = build_pharmacy_context(question, all_medicines)
    lab_tests_context = build_lab_tests_context(question, all_tests)
 
    embed_resp = client.embeddings.create(input=question, model="text-embedding-3-small")
    raw_results = (
        db.query(KnowledgeBase)
        .filter(KnowledgeBase.hospital_id == hospital_id)
        .order_by(KnowledgeBase.embedding.cosine_distance(embed_resp.data[0].embedding))
        .limit(3).all()
    )
    kb_context, chunks_included = build_kb_context(raw_results)
 
    lang_instruction = (
        build_system_prompt_malayalam()
        if (request.language == "ml" and not force_english)
        else build_system_prompt_english()
    )
 
    fallback_instruction = build_fallback_instruction(
        doctors_found=doctors_included,
        kb_chunks=chunks_included,
        has_pharmacy=len(all_medicines) > 0,
        has_labs=len(all_tests) > 0,
    )
 
    # ── Pinned doctor (mid-booking, existing logic unchanged) ─────────────
    pinned_doctor_context = ""
    if request.history:
        for msg in reversed(request.history):
            id_match = re.search(r"\[ID:\s*(\d+)\]", msg.content)
            if id_match:
                pin_id = int(id_match.group(1))
                pinned = db.query(Doctor).filter(
                    Doctor.id == pin_id,
                    Doctor.hospital_id == hospital_id,   # always tenant-scoped
                ).first()
                if pinned:
                    status = check_doctor_availability_db(pinned, db, datetime.now())
                    pinned_doctor_context = (
                        f"SELECTED DOCTOR (already confirmed by patient):\n"
                        f"- [ID: {pinned.id}] Dr. {pinned.name} "
                        f"({pinned.department}): {status}\n"
                    )
                break
 
    # ── NEW: Patient personalisation block ────────────────────────────────
    patient_ctx       = _load_patient_ctx(hospital_id, session_token)
    patient_ctx_block = _build_patient_ctx_block(patient_ctx)
 
    # NOTE: hospital.system_prompt is already injected via `hospital.system_prompt or ""`
    # below (Item 4 check — confirmed it is being used).
 
    parts = [
        f"You are Arogya, the AI Assistant for {hospital.name}.",
        f"Current Date: {prompt_date_str}",
        (
            "DATE RESOLUTION RULES (follow these exactly, every time):\n"
            f"- Treat \"{prompt_date_str}\" as ground truth for today. Ignore any other "
            "notion of the current date or year.\n"
            "- If the patient gives a date with NO year (e.g. \"July 10\", \"next Monday\", "
            "\"the 15th\"), resolve it to the NEAREST occurrence of that date on or after "
            "today's date above — this almost always means the current year, or next year "
            "only if that month/day has already occurred this year.\n"
            "- NEVER assume a year from your own training data (e.g. 2023, 2024, 2025) when "
            "the patient doesn't state one. Only use a year the patient explicitly typed.\n"
            "- Only tell a patient a date \"has already passed\" if it is chronologically "
            "before the Current Date stated above — double check the year you inferred "
            "before saying this.\n"
            "- When calling book_appointment, preferred_date must be YYYY-MM-DD using the "
            "year resolved by these rules."
        ),
        "",
        hospital.system_prompt or "",
        "",
        lang_instruction,
        "",
        patient_ctx_block,          # ← NEW: injected here, before doctor context
        pinned_doctor_context,
        doctor_context,
    ]
    if pharmacy_context:
        parts.extend(["", pharmacy_context])
    if lab_tests_context:
        parts.extend(["", lab_tests_context])
    if kb_context:
        parts.extend(["", "ADDITIONAL KNOWLEDGE BASE:", kb_context])
    parts.extend(["", fallback_instruction])
 
    system_prompt = "\n".join(parts)
 
    prompt_chars = len(system_prompt)
    if prompt_chars > SYSTEM_PROMPT_WARN_CHARS:
        logger.warning(
            "System prompt over soft limit hospital_id=%s: %d chars (~%d tokens) "
            "doctors=%d kb=%d",
            hospital_id, prompt_chars, prompt_chars // 4,
            doctors_included, chunks_included,
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

    RECENT_TURNS = 4          # always pass last 4 turns verbatim
    SUMMARY_THRESHOLD = 6     # only summarise if there are more than this many total messages

    recent = history[-(RECENT_TURNS * 2):]
    older  = history[:-(RECENT_TURNS * 2)]

    messages = []

    # If there are older turns worth summarising, collapse them into one system note
    if len(older) >= SUMMARY_THRESHOLD:
        topics = []
        for m in older:
            if m.role == "user":
                topics.append(m.content[:120])
        if topics:
            summary = "Earlier in this conversation the patient asked about: " + "; ".join(topics[-4:])
            messages.append({"role": "system", "content": summary})

    # Ensure we start on a user turn
    if recent and recent[0].role != "user":
        recent = recent[1:]

    messages.extend({"role": m.role, "content": m.content} for m in recent)
    return messages


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
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    doctors = db.query(Doctor).filter(Doctor.hospital_id == hospital_id).all()
    has_kb = db.query(KnowledgeBase).filter(KnowledgeBase.hospital_id == hospital_id).first() is not None
    has_pharmacy = db.query(Medicine).filter(Medicine.hospital_id == hospital_id).first() is not None
    has_labs = db.query(LabTest).filter(LabTest.hospital_id == hospital_id).first() is not None
    dept_names = sorted({d.department for d in doctors if d.department})

    hospital_name = hospital.name or "this hospital"

    en_caps = [
        "🩺 Check **doctor availability** — today or any day",
        f"📋 Browse doctors by department — {', '.join(dept_names) if dept_names else 'General'}",
        "📅 **Book an appointment** with any available doctor",
    ]
    ml_caps = [
        "🩺 **ഡോക്ടറുടെ ലഭ്യത** പരിശോധിക്കുക — ഇന്ന് അല്ലെങ്കിൽ ഏത് ദിവസവും",
        f"📋 വിഭാഗം അനുസരിച്ച് ഡോക്ടർമാരെ കണ്ടെത്തുക — {', '.join(dept_names) if dept_names else 'General'}",
        "📅 ഏത് ഡോക്ടറുടെ അടുത്തും **അപ്പോയിന്റ്മെന്റ്** ബുക്ക് ചെയ്യുക",
    ]

    if has_pharmacy:
        en_caps.append("💊 Look up **medicines** — availability and details")
        ml_caps.append("💊 **മരുന്നുകൾ** പരിശോധിക്കുക — ലഭ്യതയും വിവരങ്ങളും")

    if has_labs:
        en_caps.append("🔬 Check **lab tests** — what's offered and pricing")
        ml_caps.append("🔬 **ലാബ് ടെസ്റ്റുകൾ** — എന്തൊക്കെ ഉണ്ട്, വിലവിവരം")

    if has_kb:
        en_caps.append("🏥 Answer questions about hospital **timings, services & contact**")
        ml_caps.append("🏥 ആശുപത്രി **സമയം, സേവനങ്ങൾ, ബന്ധപ്പെടൽ** സംബന്ധിച്ച ചോദ്യങ്ങൾ")

    en_msg = "\n".join([
        f"👋 Hello! I am **Arogya**, the AI assistant for **{hospital_name}**.",
        "",
        "Here is what I can help you with:",
        *[f"- {c}" for c in en_caps],
        "",
        "Type or tap the mic to speak 🎤",
    ])

    ml_msg = "\n".join([
        f"👋 നമസ്കാരം! ഞാൻ **ആരോഗ്യ**, **{hospital_name}**-ന്റെ AI അസിസ്റ്റന്റ്.",
        "",
        "ഞാൻ ഇവ സഹായിക്കാം:",
        *[f"- {c}" for c in ml_caps],
        "",
        "ടൈപ്പ് ചെയ്യൂ അല്ലെങ്കിൽ മൈക്ക് അമർത്തി സംസാരിക്കൂ 🎤",
    ])

    return {"en": en_msg, "ml": ml_msg}


@router.get("/suggestions/{hospital_id}")
async def get_suggestions(hospital_id: int, db: Session = Depends(get_db)):
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    doctors = db.query(Doctor).filter(Doctor.hospital_id == hospital_id).all()
    has_pharmacy = db.query(Medicine).filter(Medicine.hospital_id == hospital_id).first() is not None
    has_labs = db.query(LabTest).filter(LabTest.hospital_id == hospital_id).first() is not None
    dept_names = sorted({d.department for d in doctors if d.department})

    en_suggestions = ["Which doctors are available today?"]
    ml_suggestions = ["ഇന്ന് ഏത് ഡോക്ടർ ഉണ്ട്?"]

    for dept in dept_names[:2]:
        en_suggestions.append(f"Is there a {dept} doctor today?")
        ml_suggestions.append(f"ഇന്ന് {dept} ഡോക്ടർ ഉണ്ടോ?")

    if has_pharmacy:
        en_suggestions.append("What medicines are available?")
        ml_suggestions.append("എന്തൊക്കെ മരുന്നുകൾ ഉണ്ട്?")

    if has_labs:
        en_suggestions.append("What lab tests do you offer?")
        ml_suggestions.append("എന്തൊക്കെ ലാബ് ടെസ്റ്റുകൾ ഉണ്ട്?")

    en_suggestions.append("Book an appointment")
    ml_suggestions.append("അപ്പോയിന്റ്മെന്റ് ബുക്ക് ചെയ്യണം")

    return {"en": en_suggestions[:4], "ml": ml_suggestions[:4]}


@router.post("/ingest")
async def ingest_knowledge(request: IngestRequest, db: Session = Depends(get_db)):
    try:
        resp = client.embeddings.create(input=request.text, model="text-embedding-3-small")
        db.add(KnowledgeBase(
            hospital_id=request.hospital_id,
            content=request.text,
            entry_type=request.entry_type,   # ← add this line
            embedding=resp.data[0].embedding,
            created_at=datetime.utcnow()
        ))
        db.commit()
        return {"status": "success", "message": "Knowledge added to Arogya's brain"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...), hospital_id: int = Form(...), entry_type: str = Form("fact"),db: Session = Depends(get_db)):
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
# ADD  entry_type=entry_type,  to the KnowledgeBase(...) call
            db.add(KnowledgeBase(hospital_id=hospital_id, content=content, entry_type=entry_type, embedding=embedding, created_at=datetime.utcnow()))        
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
    # NOTE: This endpoint is NOT used by any current frontend client.
    # All production frontend components (iris/chat-bot-ui.tsx, ChatPreview.tsx,
    # useHospitalChat.tsx) use /chat-stream exclusively.
    # Kept as a simple non-streaming endpoint for internal testing and scripts only.
    # Do not add frontend-facing features here without also implementing them in
    # /chat-stream — that is the live path for real users.
    # Last confirmed no-frontend-caller: 2026-07-21 (grep of frontend/src confirmed zero hits).
    _turn_ctx = _update_patient_ctx(
        request.hospital_id,
        request.session_token,
        language=request.language,
        question_en=request.question,
        history=request.history or [],
        db=db,
    )
    _, openai_messages, _ = build_context(request, db, force_english=False, session_token=request.session_token)

    # For Malayalam, prepend the English question as a hidden note for context retrieval
    # but the system prompt already instructs the model to reply in Malayalam
    if request.language == "ml":
        english_question = await _translate_async(request.question, "ml", "en")
        openai_messages[-1]["content"] = (
            f"[User asked in Malayalam: {request.question}]\n"
            f"[English translation for your reference: {english_question}]\n"
            f"Reply in Malayalam only."
        )

    ai_response = client.chat.completions.create(model=OPENAI_MODEL, messages=openai_messages)
    answer = ai_response.choices[0].message.content or ""

    usage = ai_response.usage
    db.add(UsageLedger(
        hospital_id=request.hospital_id, endpoint="/chat",
        prompt_tokens=usage.prompt_tokens, completion_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens, estimated_cost=(usage.total_tokens / 1_000_000) * 0.15
    ))
    db.commit()
    if _turn_ctx.get("_is_new_session"):
        if hospital := db.query(Hospital).filter(Hospital.id == request.hospital_id).first():
            if hospital.welcome_message:
                answer = f"{hospital.welcome_message}\n\n{answer}"
    return {"answer": answer}


# =============================================================================
# INTENT CLASSIFICATION
# =============================================================================

async def normalise_booking_input(
    raw_message: str,
    current_field: str,
    conversation_context: str = ""
) -> dict:
    today_str = datetime.now().strftime("%A, %B %d, %Y")
    system_prompt = f"""You are a data extraction assistant for a hospital booking system.

Today's date is {today_str}. Use this as ground truth for any date reasoning below —
never assume a year from your own training data.

The assistant is currently collecting: {current_field}
Recent conversation:
{conversation_context}

The user just said: "{raw_message}"

Your job is to interpret what the user means and return a JSON object with these fields:
- "intent": one of "provide" (giving the requested info), "correct" (wants to change something already given), "cancel" (wants to stop entirely), "unclear" (genuinely ambiguous)
- "field_to_correct": if intent is "correct", which field they want to change. One of: phone, name, age, date, time, doctor. Otherwise null.
- "normalised_value": if intent is "provide", the cleaned value ready to use. For phone numbers, return only digits. For names, return only the name part (strip "and she is X years old" etc). For age, return only the number. For dates, return YYYY-MM-DD (see date rules below). Otherwise null.
- "reason": brief note if intent is "unclear" or "correct"

CRITICAL RULES for normalisation:
- Phone numbers: Convert spoken/spaced digits to a single string of digits. "94 67 48 74 48" → "9467487448". Remove all spaces, dashes, brackets.
- Names: Extract only the person's name. "Reetha and she is 50 years old" → "Reetha". "My name is John" → "John".
- Ages: Extract only the number. "I am 45 years old" → "45". "forty five" → "45".
- Dates: If the user gives a date with NO year (e.g. "July 8", "8 july", "next Monday"), resolve
  it to the NEAREST occurrence of that date on or after Today's date above (current year, or
  next year only if that month/day has already occurred this year). NEVER assume a year from
  your own training data. Return the result as YYYY-MM-DD. Only treat a date as being in the
  past if it is chronologically before Today's date above once the year has been correctly resolved.
- Corrections: "no my number is wrong" → intent=correct, field_to_correct=phone.
- True cancellations: "I don't want to book anymore" → intent=cancel.
- "no" alone during confirmation step: treat as intent=correct (patient wants to change something), NOT cancel.

Return ONLY valid JSON, no markdown, no explanation."""

    try:
        resp = await async_client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.0,
            max_tokens=150,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": raw_message}
            ]
        )
        result = json.loads(resp.choices[0].message.content)
        return {
            "intent": result.get("intent", "unclear"),
            "field_to_correct": result.get("field_to_correct"),
            "normalised_value": result.get("normalised_value"),
            "reason": result.get("reason", "")
        }
    except Exception as e:
        logger.warning("normalise_booking_input failed: %s", e)
        return {
            "intent": "provide",
            "field_to_correct": None,
            "normalised_value": raw_message,
            "reason": ""
        }


async def classify_user_intent(user_message: str, history: list = []) -> str:
    """
    Classifies user intent.  Importantly: if the user is mid-booking but asks
    a general information question, this returns OTHER so that the topic switch
    is respected and context bleed is avoided.
    """
    history_snippet = ""
    if history:
        recent = history[-4:]
        history_snippet = "\n".join(
            f"{'Assistant' if m.role == 'assistant' else 'User'}: {m.content[:200]}"
            for m in recent
        )

    system_prompt = """You are an intent classification engine for a hospital chatbot.
Read the conversation and the latest user message, then output exactly ONE word.

Categories:
STATUS  - User is asking to CHECK an existing appointment status or reference number.
BOOKING - User wants to book/schedule an appointment, OR is providing booking details (name, phone, age, date) in the middle of a booking flow.
CANCEL  - User wants to cancel or stop an ongoing booking process.
OTHER   - General hospital questions: asking about doctors, medicines, lab tests, timings, availability, departments, or any informational question.

STRICT RULES:
- If the user changes the subject to ask a general question (doctors, medicines, lab tests, timings), output: OTHER — even if you were in the middle of booking.
- If the user asks "is there a doctor on Wednesday" or similar day/availability question, output: OTHER (not BOOKING).
- Only output BOOKING if the user explicitly says they want to book, or is actively providing details (name/phone/age) for a booking that's already in progress.
- Only output the single category word, nothing else."""

    context = (
        f"Conversation:\n{history_snippet}\n\nLatest message: {user_message}"
        if history_snippet
        else f"Message: {user_message}"
    )

    try:
        resp = await async_client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.0,
            max_tokens=5,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context}
            ]
        )
        intent = resp.choices[0].message.content.strip().upper()
        return intent if intent in {"STATUS", "BOOKING", "CANCEL", "OTHER"} else "OTHER"
    except Exception as e:
        logger.warning("Intent classification failed: %s", e)
        return "OTHER"


# =============================================================================
# CHAT STREAM
# =============================================================================

@router.post("/chat-stream")
async def chat_stream(request: ChatRequest, db: Session = Depends(get_db)):
    is_malayalam = request.language == "ml"

    # For Malayalam: translate to English for intent classification and context
    # retrieval, but then generate the Malayalam response natively (no post-translate).
    english_question = request.question
    if is_malayalam:
        english_question = await _translate_async(request.question, "ml", "en")
        logger.info("[Translation] ml->en: %r -> %r", request.question[:60], english_question[:60])

    intent = await classify_user_intent(english_question, request.history or [])

    # NOTE: this was previously a dead string literal (_PATIENT_CTX_CALL) that
    # was never executed, so patient context was never updated on the
    # streaming path — only read. Fixed as part of §1.1.
    _turn_ctx = _update_patient_ctx(
        request.hospital_id,
        request.session_token,
        language=request.language,
        question_en=english_question,
        history=request.history or [],
        db=db,
    )

    # If the patient is mid-relevance-gate, their short answers ("yes", "joint pain")
    # will likely be classified as OTHER. Force it to BOOKING to keep them in the gate.
    _active_stage = _turn_ctx.get("relevance_stage")
    if _active_stage in ("asked_referral", "asked_prior_docs", "asked_symptom") and intent != "CANCEL":
        intent = "BOOKING"
        logger.info("[Intent] Overridden to BOOKING because patient is mid-relevance-gate (%s)", _active_stage)

    logger.info("[Intent] %s -> %s", english_question[:60], intent)

    async def event_generator() -> AsyncGenerator[str, None]:
        pt = ct = tt = 0
        if _turn_ctx.get("_is_new_session"):
            hospital_for_welcome = db.query(Hospital).filter(Hospital.id == request.hospital_id).first()
            if hospital_for_welcome and hospital_for_welcome.welcome_message:
                yield f"data: {json.dumps(hospital_for_welcome.welcome_message)}\n\n"
        # ── CANCEL ───────────────────────────────────────────────────────────
        if intent == "CANCEL":
            msg = (
                "ശരി, ഞാൻ ബുക്കിംഗ് നിർത്തി. മറ്റേതെങ്കിലും സഹായം വേണോ?"
                if is_malayalam
                else "Okay, I've cancelled any active requests. How else can I help you?"
            )
            yield f"data: {json.dumps(msg)}\n\n"
            yield "data: [DONE]\n\n"
            return

        # ── STATUS CHECK ─────────────────────────────────────────────────────
        if intent == "STATUS":
            history_text = " ".join(
                m.content for m in (request.history or [])[-6:]
            )
            combined = re.sub(r"[\s\-\(\)\.]", "", english_question + " " + history_text)
            phone_match = re.search(r"\+?\d{10,15}", combined)

            if not phone_match:
                msg = (
                    "അപ്പോയിന്റ്മെന്റ് സ്റ്റാറ്റസ് നോക്കാം! ബുക്ക് ചെയ്തപ്പോൾ ഉപയോഗിച്ച 10 അക്ക ഫോൺ നമ്പർ തരാമോ?"
                    if is_malayalam
                    else "I can check your appointment status! Please share the 10-digit phone number you used when booking."
                )
                yield f"data: {json.dumps(msg)}\n\n"
                yield "data: [DONE]\n\n"
                return

            extracted_phone = phone_match.group(0)
            appts = (
                db.query(Appointment)
                .filter(
                    Appointment.hospital_id == request.hospital_id,
                    Appointment.patient_phone == extracted_phone
                )
                .order_by(Appointment.created_at.desc())
                .limit(3)
                .all()
            )

            if not appts:
                msg = (
                    f"{extracted_phone} എന്ന നമ്പരിൽ അപ്പോയിന്റ്മെന്റ് കണ്ടില്ല. നമ്പർ ശരിയാണോ എന്ന് ഒന്ന് നോക്കൂ, അല്ലെങ്കിൽ reception-ൽ വിളിക്കൂ."
                    if is_malayalam
                    else f"I couldn't find any appointments for the number {extracted_phone}. Please double-check or contact the reception desk."
                )
                yield f"data: {json.dumps(msg)}\n\n"
                yield "data: [DONE]\n\n"
                return

            reply_lines = [
                "നിങ്ങളുടെ അപ്പോയിന്റ്മെന്റ് വിവരങ്ങൾ:\n" if is_malayalam
                else "Here is the status of your recent appointments:\n"
            ]
            for a in appts:
                doc = db.query(Doctor).filter(Doctor.id == a.doctor_id).first()
                doc_name = doc.name if doc else "Unknown"
                status_str = {
                    "pending":  "⏳ Pending — hospital will call to confirm",
                    "approved": f"✅ Confirmed for **{a.confirmed_time}**",
                    "rejected": f"❌ Rejected ({a.rejection_reason or 'no reason given'})"
                }.get(a.status, a.status)
                reply_lines.append(
                    f"👨‍⚕️ **Dr. {doc_name}** — {a.preferred_date} ({a.time_of_day})\n"
                    f"   Status: {status_str}\n"
                    f"   Reference: `{a.reference_number}`\n"
                )

            reply = "\n".join(reply_lines)
            if is_malayalam:
                reply = await _translate_async(reply, "en", "ml")
            yield f"data: {json.dumps(reply)}\n\n"
            yield "data: [DONE]\n\n"
            return

        # ── BOOKING & GENERAL CHAT ────────────────────────────────────────────
        #
        # For Malayalam: build context using the English translation, but instruct
        # the model to generate its reply directly in Malayalam.
        # This completely eliminates the Google Translate post-processing step
        # and the garbled/unnatural phrasing it produces.
        #

        # ── FEATURE 4: RELEVANCE GATE ─────────────────────────────────────────
        # Only active when hospital.relevance_criteria is set.
        # Gate runs BEFORE any doctor/slot collection begins.
        # Uses patient_ctx for state so it survives across turns without a
        # separate Redis key.
        if intent == "BOOKING":
            from app.services.relevance import check_relevance, RelevanceVerdict, check_referral_intent

            # Re-fetch hospital for the gate (already fetched in build_context below,
            # but we need it here before that call).
            _gate_hospital = db.query(Hospital).filter(
                Hospital.id == request.hospital_id
            ).first()
            _criteria = (_gate_hospital.relevance_criteria or "").strip() if _gate_hospital else ""

            if _criteria:
                _rctx = _load_patient_ctx(request.hospital_id, request.session_token)

                # Detect a new booking attempt (patient already completed one this session)
                if _is_new_booking_attempt(_rctx):
                    logger.info(
                        "[RelevanceGate] New booking attempt detected for hospital_id=%s — resetting gate",
                        request.hospital_id,
                    )
                    _rctx = _reset_relevance_gate(_rctx)
                    _save_patient_ctx(request.hospital_id, request.session_token, _rctx)

                _stage = _rctx.get("relevance_stage")
                _answers = _rctx.get("relevance_answers", {})

                if _stage is None:
                    # ── Q1: Has a doctor referred you? ──────────────────────
                    _rctx["relevance_stage"] = "asked_referral"
                    _save_patient_ctx(request.hospital_id, request.session_token, _rctx)
                    q1 = (
                        "ഒരു ചോദ്യം: ഒരു ഡോക്ടർ നിങ്ങളെ ഞങ്ങളുടെ ക്ലിനിക്കിലേക്ക് refer ചെയ്തിട്ടുണ്ടോ?"
                        if is_malayalam
                        else "Before I proceed with the booking, I have a quick question: Has a doctor referred you to our clinic?"
                    )
                    yield f"data: {json.dumps(q1)}\n\n"
                    yield "data: [DONE]\n\n"
                    return

                elif _stage == "asked_referral":
                    # Patient just answered Q1 — record and branch
                    _answers["referral"] = english_question
                    _rctx["relevance_answers"] = _answers

                    referral_positive = await check_referral_intent(
                        patient_answer=english_question,
                        hospital_id=request.hospital_id
                    )
                    if referral_positive:
                        # Referred patients are always relevant — skip remaining questions
                        verdict_dict = {
                            "is_relevant": True,
                            "needs_staff_review": False,
                            "reason": "Patient was referred by a doctor — treated as relevant.",
                        }
                        _rctx["relevance_stage"] = "done"
                        _rctx["relevance_verdict"] = verdict_dict
                        _save_patient_ctx(request.hospital_id, request.session_token, _rctx)
                        # Fall through to normal booking below (no yield/return here)
                    else:
                        # Ask Q2: which specialists have they seen?
                        _rctx["relevance_stage"] = "asked_prior_docs"
                        _save_patient_ctx(request.hospital_id, request.session_token, _rctx)
                        q2 = (
                            "ഞങ്ങൾ മനസ്സിലാക്കാൻ ശ്രമിക്കുകയാണ്: ഈ ആരോഗ്യ പ്രശ്നത്തിന് ഇതിനുമുമ്പ് ഏത് ഡോക്ടർ/സ്പെഷ്യലിസ്റ്റ് ആണ് നോക്കിയിട്ടുള്ളത്?"
                            if is_malayalam
                            else "To help us prepare, could you briefly mention which doctors or specialists you've consulted for this condition before?"
                        )
                        yield f"data: {json.dumps(q2)}\n\n"
                        yield "data: [DONE]\n\n"
                        return

                elif _stage == "asked_prior_docs":
                    # Patient answered Q2 — record and ask Q3
                    _answers["prior_docs"] = english_question
                    _rctx["relevance_answers"] = _answers
                    _rctx["relevance_stage"] = "asked_symptom"
                    _save_patient_ctx(request.hospital_id, request.session_token, _rctx)
                    q3 = (
                        "നന്ദി. ഒടുവിലായി, ഇന്ന് നിങ്ങൾ ഏറ്റവും അനുഭവിക്കുന്ന പ്രധാന ലക്ഷണം ഒന്ന് ചുരുക്കി പറയാമോ?"
                        if is_malayalam
                        else "Thank you. Finally, could you briefly describe your main symptom or concern that brings you here today?"
                    )
                    yield f"data: {json.dumps(q3)}\n\n"
                    yield "data: [DONE]\n\n"
                    return

                elif _stage == "asked_symptom":
                    # Patient answered Q3 — run the LLM relevance check
                    _answers["symptom"] = english_question
                    _rctx["relevance_answers"] = _answers

                    verdict: RelevanceVerdict = await check_relevance(
                        relevance_criteria=_criteria,
                        patient_answers=_answers,
                        hospital_id=request.hospital_id,
                    )
                    verdict_dict = {
                        "is_relevant": verdict.is_relevant,
                        "needs_staff_review": verdict.needs_staff_review,
                        "reason": verdict.reason,
                    }
                    _rctx["relevance_stage"] = "done"
                    _rctx["relevance_verdict"] = verdict_dict
                    _save_patient_ctx(request.hospital_id, request.session_token, _rctx)
                    # Fall through to normal booking below

                # _stage == "done": gate complete, fall through to normal booking

        # ── End relevance gate ────────────────────────────────────────────────
        context_question = english_question if is_malayalam else request.question
        translated_request = request.model_copy(update={
            "question": context_question,
            # Keep language="ml" so build_context uses the Malayalam system prompt
            "language": request.language,
        })
        system_prompt, openai_messages, hospital = build_context(
            translated_request, db, force_english=False, session_token=request.session_token
        )

        # For Malayalam, replace the final user message with a bilingual hint so
        # the model has the original Malayalam text for nuance AND the English for
        # understanding structured data references.
        if is_malayalam:
            openai_messages[-1]["content"] = (
                f"{request.question}\n"
                f"[English reference: {english_question}]"
            )

        booking_field_keywords = {
            "phone":  ["phone", "number", "mobile", "contact"],
            "name":   ["name", "patient's full name", "full name"],
            "age":    ["age", "how old", "date of birth"],
            "date":   ["date", "prefer", "which day"],
            "time":   ["morning", "afternoon", "evening", "time of day"],
            "doctor": ["doctor", "which doctor", "department"],
        }
        current_field = None
        if request.history:
            last_assistant = next(
                (m.content.lower() for m in reversed(request.history) if m.role == "assistant"),
                ""
            )
            matched_fields = [
                field for field, keywords in booking_field_keywords.items()
                if any(kw in last_assistant for kw in keywords)
            ]
            # A genuine single-field question ("What's the patient's phone
            # number?") matches exactly one category. A confirmation summary
            # ("Name: X, Age: Y, Phone: Z... is this correct?") legitimately
            # mentions several fields at once and was being misread as "still
            # collecting phone" (first match in dict order) — which hijacked
            # the user's confirmation reply ("yes correct") into the
            # single-field normaliser instead of letting the main model
            # handle it as a booking confirmation. Only treat this as an
            # active single-field question when exactly one category matched.
            if len(matched_fields) == 1:
                current_field = matched_fields[0]

        processed_question = context_question
        if current_field and intent == "BOOKING":
            context_snippet = "\n".join(
                f"{'Bot' if m.role == 'assistant' else 'Patient'}: {m.content}"
                for m in (request.history or [])[-4:]
            )
            normalised = await normalise_booking_input(
                english_question, current_field, context_snippet
            )
            logger.info("[Normalise] field=%s intent=%s value=%r",
                        current_field, normalised["intent"], normalised["normalised_value"])

            if normalised["intent"] == "cancel":
                msg = (
                    "ശരി, ബുക്കിംഗ് നിർത്തി. മറ്റേതെങ്കിലും സഹായം വേണോ?"
                    if is_malayalam
                    else "Okay, I've cancelled the booking process. Is there anything else I can help you with?"
                )
                yield f"data: {json.dumps(msg)}\n\n"
                yield "data: [DONE]\n\n"
                return

            if normalised["intent"] == "correct":
                field = normalised.get("field_to_correct", current_field)
                en_prompts = {
                    "phone":  "Of course! Please provide the correct phone number.",
                    "name":   "Of course! What is the correct patient name?",
                    "age":    "Of course! What is the correct age?",
                    "date":   "Of course! Which date would you prefer?",
                    "time":   "Of course! Morning, afternoon, or evening?",
                    "doctor": "Of course! Which doctor would you like to see?",
                }
                ml_prompts = {
                    "phone":  "ശരി! ശരിയായ ഫോൺ നമ്പർ പറയൂ.",
                    "name":   "ശരി! രോഗിയുടെ ശരിയായ പേര് എന്താണ്?",
                    "age":    "ശരി! ശരിയായ പ്രായം എത്ര?",
                    "date":   "ശരി! ഏത് തീയതി വേണം?",
                    "time":   "ശരി! രാവിലെ, ഉച്ചക്ക്, അതോ വൈകിട്ട്?",
                    "doctor": "ശരി! ഏത് ഡോക്ടറെ കാണണം?",
                }
                msg = (ml_prompts if is_malayalam else en_prompts).get(
                    field, "ശരി! ശരിയായ വിവരം പറയൂ." if is_malayalam else "Of course! Please provide the correct information."
                )
                yield f"data: {json.dumps(msg)}\n\n"
                yield "data: [DONE]\n\n"
                return

            if normalised["intent"] == "provide" and normalised["normalised_value"]:
                processed_question = normalised["normalised_value"]
                if isinstance(processed_question, dict):
                    processed_question = json.dumps(processed_question)
                else:
                    processed_question = str(processed_question)
                    
                openai_messages[-1]["content"] = (
                    processed_question
                    if not is_malayalam
                    else f"{request.question}\n[English reference: {processed_question}]"
                )

        # Agent instructions (language-aware)
        if is_malayalam:
            agent_instructions = """
APPOINTMENT BOOKING CAPABILITY (for Malayalam conversations):
You can book appointments. Collect these details one at a time, asking in simple natural Malayalam:
1. Doctor (use [ID: X] from the doctor list to identify)
2. Preferred date — ask for a specific date or day of the week
3. Time of day (morning/afternoon/evening — use: രാവിലെ / ഉച്ചക്ക് / വൈകിട്ട്)
4. Patient's full name
5. Patient's age
6. Phone number (10 digits)

VALIDATION:
- Phone: exactly 10 digits. If wrong, ask again in Malayalam.
- Date: must be a future date. Correctly interpret day names: ഞായർ=Sunday, തിങ്കൾ=Monday, ചൊവ്വ=Tuesday, ബുധൻ=Wednesday, വ്യാഴം=Thursday, വെള്ളി=Friday, ശനി=Saturday.
- Before confirming, show a summary in Malayalam and ask "ഈ വിവരങ്ങൾ ശരിയാണോ?" (Is this correct?)

IMPORTANT: Answer all general questions (doctors, tests, medicines, timings) directly and helpfully.
Only trigger 'book_appointment' after the patient confirms ALL 6 details."""
        else:
            agent_instructions = """
APPOINTMENT BOOKING CAPABILITY:
You can book appointments for patients. Collect these details naturally, one at a time:
1. Doctor (use the [ID: X] from the doctor list above to identify them)
2. Preferred date (ask for a specific date like "April 20" or "next Monday")
3. Time of day (morning, afternoon, or evening)
4. Patient's full name (name only)
5. Patient's age (number only, 1-120)
6. Phone number (must be exactly 10 digits for Indian numbers)

VALIDATION RULES:
- Phone: exactly 10 digits. If wrong length, ask again.
- Name: extract only the name part.
- Date: must be a future date.

IMPORTANT:
- Answer general questions normally using the knowledge base.
- Only trigger 'book_appointment' once you have confirmed ALL 6 details with the patient.
- Before triggering, show a confirmation summary and ask the patient to confirm."""

        _verdict = _turn_ctx.get("relevance_verdict")
        if _verdict:
            force_booking_rule = "\n- IMPORTANT: The patient's reason for visiting has already been evaluated. Do NOT refuse the booking even if their symptoms seem unrelated to this clinic's specialty. Proceed to collect appointment details."
            agent_instructions += force_booking_rule

        openai_messages[0]["content"] += f"\n\n{agent_instructions}"

        tools = [{
            "type": "function",
            "function": {
                "name": "book_appointment",
                "description": (
                    "Trigger ONLY when the patient has confirmed all 6 details "
                    "(doctor_id, date, time, name, age, phone). "
                    "Do NOT trigger if any detail is missing or unconfirmed."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "doctor_id":      {"type": "integer", "description": "The numeric ID from [ID: X] in the doctor list"},
                        "preferred_date": {"type": "string",  "description": "Date in YYYY-MM-DD format"},
                        "time_of_day":    {"type": "string",  "enum": ["morning", "afternoon", "evening"]},
                        "patient_name":   {"type": "string",  "description": "Patient's full name only"},
                        "patient_age":    {"type": "string",  "description": "Patient's age as a number"},
                        "patient_phone":  {"type": "string",  "description": "10-digit phone number, digits only"}
                    },
                    "required": ["doctor_id", "preferred_date", "time_of_day",
                                 "patient_name", "patient_age", "patient_phone"]
                }
            }
        }]

        try:
            stream = await async_client.chat.completions.create(
                model=OPENAI_MODEL_ML if is_malayalam else OPENAI_MODEL,
                messages=openai_messages,
                tools=tools,
                temperature=0.3,
                stream=True,
                stream_options={"include_usage": True}
            )
        except Exception as e:
            logger.exception("[chat-stream] OpenAI call failed: %s", e)
            err = (
                "ക്ഷമിക്കണം, ഒരു ബന്ധ പ്രശ്നം ഉണ്ട്. ദയവായി വീണ്ടും ശ്രമിക്കൂ."
                if is_malayalam
                else "Sorry, I'm having trouble connecting right now. Please try again."
            )
            yield f"data: {json.dumps(err)}\n\n"
            yield "data: [DONE]\n\n"
            return

        tool_call_name = ""
        tool_call_args = ""
        is_tool_call = False

        async for chunk in stream:
            if chunk.usage:
                pt = chunk.usage.prompt_tokens
                ct = chunk.usage.completion_tokens
                tt = chunk.usage.total_tokens

            delta = chunk.choices[0].delta if chunk.choices else None
            if not delta:
                continue

            if delta.tool_calls:
                is_tool_call = True
                tc = delta.tool_calls[0]
                if tc.function.name:
                    tool_call_name += tc.function.name
                if tc.function.arguments:
                    tool_call_args += tc.function.arguments
            elif delta.content and not is_tool_call:
                # Stream tokens directly — no post-translation needed since
                # the LLM generates Malayalam natively now.
                yield f"data: {json.dumps(delta.content)}\n\n"

        # ── Handle tool call (booking) ────────────────────────────────────────
        if is_tool_call and tool_call_name == "book_appointment":
            try:
                from app.services.booking_rules import validate_booking, get_booking_config
                from app.services.email import notify_staff_new_appointment

                args = json.loads(tool_call_args)

                phone_digits = re.sub(r"\D", "", args.get("patient_phone", ""))
                if len(phone_digits) < 7 or len(phone_digits) > 15:
                    err = (
                        f"ഫോൺ നമ്പർ '{args.get('patient_phone')}' ശരിയല്ല. ദയവായി 10 അക്ക മൊബൈൽ നമ്പർ വീണ്ടും തരൂ."
                        if is_malayalam
                        else f"The phone number '{args.get('patient_phone')}' doesn't look right. Please provide the 10-digit mobile number again."
                    )
                    yield f"data: {json.dumps(err)}\n\n"
                    yield "data: [DONE]\n\n"
                    return

                age_str = re.sub(r"\D", "", str(args.get("patient_age", "")))
                if not age_str or not (1 <= int(age_str) <= 120):
                    err = (
                        "പ്രായം ശരിയല്ല. ദയവായി വീണ്ടും പറയൂ."
                        if is_malayalam
                        else "The age doesn't look right. Please confirm the patient's age."
                    )
                    yield f"data: {json.dumps(err)}\n\n"
                    yield "data: [DONE]\n\n"
                    return

                doctor = db.query(Doctor).filter(
                    Doctor.id == args["doctor_id"],
                    Doctor.hospital_id == request.hospital_id
                ).first()

                if not doctor:
                    err = (
                        "ആ ഡോക്ടറെ system-ൽ കണ്ടില്ല. ഏത് ഡോക്ടറെ കാണണം?"
                        if is_malayalam
                        else "I couldn't find that doctor in the system. Which doctor would you like to see?"
                    )
                    yield f"data: {json.dumps(err)}\n\n"
                    yield "data: [DONE]\n\n"
                    return

                ok, error_msg = validate_booking(hospital, doctor, args["preferred_date"], db)
                if not ok:
                    if is_malayalam:
                        error_msg = await _translate_async(error_msg, "en", "ml")
                    yield f"data: {json.dumps(error_msg)}\n\n"
                    yield "data: [DONE]\n\n"
                    return

                appt = Appointment(
                    hospital_id=request.hospital_id,
                    doctor_id=args["doctor_id"],
                    patient_name=args["patient_name"].strip(),
                    patient_age=age_str,
                    patient_phone=phone_digits,
                    preferred_date=args["preferred_date"],
                    time_of_day=args["time_of_day"].lower(),
                    status="pending"
                )

                # Feature 4: attach relevance verdict if gate ran for this hospital
                _final_ctx = _load_patient_ctx(request.hospital_id, request.session_token)
                _verdict = _final_ctx.get("relevance_verdict")
                if _verdict:
                    appt.relevance_reason   = _verdict.get("reason")
                    appt.needs_staff_review = bool(_verdict.get("needs_staff_review", False))

                db.add(appt)
                db.commit()
                db.refresh(appt)

                # Stamp booking_completed_at so a second booking attempt in this
                # session resets the relevance gate (see _is_new_booking_attempt).
                _final_ctx["booking_completed_at"] = time.time()
                _final_ctx["booking_attempt"] = _final_ctx.get("booking_attempt", 0) + 1
                _save_patient_ctx(request.hospital_id, request.session_token, _final_ctx)
                _log_task_completion(
                    request.hospital_id,
                    request.session_token,
                    _load_patient_ctx(request.hospital_id, request.session_token),
                    outcome="booking_success",
                )

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

                if is_malayalam:
                    success_msg = (
                        f"✅ **അപ്പോയിന്റ്മെന്റ് അപേക്ഷ സ്വീകരിച്ചു!**\n\n"
                        f"Reference: **{appt.reference_number}**\n"
                        f"ഡോക്ടർ: {doctor.name} ({doctor.department})\n"
                        f"തീയതി: {appt.preferred_date} — {appt.time_of_day}\n"
                        f"രോഗി: {appt.patient_name}, {appt.patient_age} വയസ്സ്\n\n"
                        f"ആശുപത്രി **{appt.patient_phone}** നമ്പരിൽ വിളിച്ച് slot confirm ചെയ്യും."
                    )
                else:
                    success_msg = (
                        f"✅ **Appointment Request Submitted!**\n\n"
                        f"Reference: **{appt.reference_number}**\n"
                        f"Doctor: {doctor.name} ({doctor.department})\n"
                        f"Date: {appt.preferred_date} — {appt.time_of_day.title()}\n"
                        f"Patient: {appt.patient_name}, age {appt.patient_age}\n\n"
                        f"The hospital will call **{appt.patient_phone}** to confirm your slot."
                    )
                if hospital.post_booking_disclaimer:
                    success_msg += f"\n\n{hospital.post_booking_disclaimer}"
                yield f"data: {json.dumps(success_msg)}\n\n"
                yield "data: [DONE]\n\n"
                return

            except json.JSONDecodeError:
                logger.error("[chat-stream] Failed to parse tool args: %r", tool_call_args)
                err = (
                    "ബുക്കിംഗ്-ൽ ഒരു error ഉണ്ടായി. ദയവായി വീണ്ടും ശ്രമിക്കൂ."
                    if is_malayalam
                    else "Something went wrong while booking. Please try again."
                )
                yield f"data: {json.dumps(err)}\n\n"
            except Exception as e:
                logger.exception("[chat-stream] Tool execution error: %s", e)
                err = (
                    "ഒരു technical error ഉണ്ടായി. ദയവായി വീണ്ടും ശ്രമിക്കൂ."
                    if is_malayalam
                    else "Sorry, there was a technical error. Please try again."
                )
                yield f"data: {json.dumps(err)}\n\n"

        yield "data: [DONE]\n\n"

        # Log usage
        if tt > 0:
            try:
                db.add(UsageLedger(
                    hospital_id=request.hospital_id,
                    endpoint="/chat-stream",
                    prompt_tokens=pt,
                    completion_tokens=ct,
                    total_tokens=tt,
                    estimated_cost=(tt / 1_000_000) * OPENAI_COST_PER_MTok
                ))
                db.commit()
            except Exception as e:
                logger.warning("[chat-stream] Usage logging failed: %s", e)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"}
    )


@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    language: str = Form("en"),
    hospital_id: int = Form(0),
    db: Session = Depends(get_db)
):
    temp_filename = f"temp_{uuid.uuid4().hex}_{file.filename}"
    try:
        with open(temp_filename, "wb") as buffer:
            buffer.write(await file.read())

        file_size = os.path.getsize(temp_filename)
        duration_seconds = file_size / (16000 * 2)
        if duration_seconds < 1.0:
            return {"transcript": ""}
        if duration_seconds > 28.0:
            return {"transcript": ""}

        if language == "ml":
            model = "saaras:v3"
            lang_code = "ml-IN"
            mode = "codemix"
        else:
            model = "saarika:v2.5"
            lang_code = "en-IN"
            mode = "transcribe"

        with open(temp_filename, "rb") as audio_file:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.sarvam.ai/speech-to-text",
                    headers={"api-subscription-key": settings.SARVAM_API_KEY},
                    data={
                        "model": model,
                        "language_code": lang_code,
                        "mode": mode,
                    },
                    files={"file": ("recording.wav", audio_file, "audio/wav")},
                )

        if not response.is_success:
            logger.error(f"Sarvam STT error: {response.status_code} {response.text}")
            raise HTTPException(status_code=502, detail="Transcription service error")

        result = response.json()
        transcript = result.get("transcript", "")
        return {"transcript": transcript}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
    finally:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

@router.get("/knowledge/{hospital_id}")
async def list_knowledge(hospital_id: int, db: Session = Depends(get_db)):
    entries = (
        db.query(KnowledgeBase)
        .filter(KnowledgeBase.hospital_id == hospital_id)
        .order_by(KnowledgeBase.created_at.desc())
        .all()
    )
    return [
        {
            "id": e.id,
            "content": e.content,
            "entry_type": getattr(e, "entry_type", "fact") or "fact",
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in entries
    ]


class UpdateKnowledgeRequest(BaseModel):
    content: str

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("content cannot be empty")
        return v


@router.patch("/knowledge/entry/{entry_id}")
async def update_knowledge_entry(entry_id: int, request: UpdateKnowledgeRequest, db: Session = Depends(get_db)):
    entry = db.query(KnowledgeBase).filter(KnowledgeBase.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")
    try:
        resp = client.embeddings.create(input=request.content, model="text-embedding-3-small")
        entry.content = request.content
        entry.embedding = resp.data[0].embedding
        db.commit()
        return {"status": "success", "message": "Entry updated"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/knowledge/entry/{entry_id}")
async def delete_knowledge_entry(entry_id: int, db: Session = Depends(get_db)):
    entry = db.query(KnowledgeBase).filter(KnowledgeBase.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")
    try:
        db.delete(entry)
        db.commit()
        return {"status": "success", "message": "Entry deleted"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))