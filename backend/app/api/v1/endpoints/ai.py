import os
import re
import json
import fitz
import logging
import unicodedata
import httpx
import uuid
from typing import List, Optional, AsyncGenerator
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator
from openai import OpenAI, AsyncOpenAI
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from fastapi import APIRouter, UploadFile, File, HTTPException
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.core.config import settings  # ← add this if not already there
from app.api.deps import get_db
from app.models.hospital import Hospital
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
BOOKING_SESSION_TTL = 600
OPENAI_MODEL        = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_COST_PER_MTok = float(os.getenv("OPENAI_COST_PER_MTok", "0.15"))
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
# Session helpers
# =============================================================================

def _session_key(hospital_id: str, session_token: str) -> str:
    return f"booking:{hospital_id}:{session_token}"


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


def check_doctor_availability_db(doctor: Doctor, db: Session, target_date: datetime) -> str:
    """Queries PostgreSQL to find out if the doctor is working today."""
    # 1. Check for leaves first
    leave = db.query(DoctorLeave).filter(
        DoctorLeave.doctor_id == doctor.id,
        DoctorLeave.date == target_date.date()
    ).first()
    if leave:
        reason = f" ({leave.reason})" if leave.reason else ""
        return f"ABSENT TODAY{reason}"

    # 2. Check regular schedule
    day_of_week = target_date.weekday() # 0=Monday, 6=Sunday
    
    # Check if ANY schedules exist for this doctor in the new system
    has_any_schedule = db.query(DoctorSchedule).filter(DoctorSchedule.doctor_id == doctor.id).first() is not None
    
    schedule = db.query(DoctorSchedule).filter(
        DoctorSchedule.doctor_id == doctor.id,
        DoctorSchedule.day_of_week == day_of_week,
        DoctorSchedule.is_active == True
    ).first()

    if schedule:
        return f"Available today from {schedule.start_time} to {schedule.end_time}"
    
    if has_any_schedule:
        # They are using the new UI, but are just not scheduled today
        return "Not scheduled to work today"
    else:
        # No new UI schedules exist yet! Fallback to the CSV base_schedule.
        base = getattr(doctor, "base_schedule", None)
        if base and base.lower() != "not specified":
            return f"Standard Timings: {base}"
        return "Timings not specified"

def build_doctor_context(question: str, hospital_id: int, db: Session) -> tuple[str, int]:
    """
    Semantic vector search for relevant doctors.
    No hardcoded synonyms — embedding handles all language variants naturally.
    """
    # Embed the question
    q_embedding = client.embeddings.create(
        input=question, model="text-embedding-3-small"
    ).data[0].embedding

    today = datetime.now()

    # Check if question is broad ("list all doctors", "who do you have")
    broad_keywords = {"all", "list", "doctors", "staff", "everyone", "available"}
    is_broad = len(set(question.lower().split()) & broad_keywords) >= 2

    if is_broad:
        # Return all doctors, unranked
        doctors = (
            db.query(Doctor)
            .filter(Doctor.hospital_id == hospital_id)
            .limit(20)
            .all()
        )
    else:
        # Semantic search — top 8 most relevant
        doctors = (
            db.query(Doctor)
            .filter(Doctor.hospital_id == hospital_id)
            .filter(Doctor.embedding != None)
            .order_by(Doctor.embedding.cosine_distance(q_embedding))
            .limit(8)
            .all()
        )
        # Fallback: if no embeddings exist yet, return first 5
        if not doctors:
            doctors = (
                db.query(Doctor)
                .filter(Doctor.hospital_id == hospital_id)
                .limit(5)
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
    """Matches user questions against the medicine database."""
    nq = normalize_name(question)
    q_tokens = set(nq.split())
    if not q_tokens or not medicines: return ""

    scored = []
    for m in medicines:
        m_text = normalize_name(f"{m.name} {m.brand_name or ''} {m.category or ''}")
        m_tokens = set(m_text.split())
        score = len(q_tokens & m_tokens)
        if score > 0:
            scored.append((score, m))

    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored: return ""

    lines = ["RELEVANT PHARMACY ITEMS:"]
    for _, m in scored[:5]: # Top 5 closest matches
        req_rx = "Prescription Required" if m.requires_prescription else "Over-the-counter"
        status = (m.stock_status or "in_stock").replace("_", " ").title()
        lines.append(f"- {m.name} ({m.brand_name or 'Generic'}): Status: {status}, Price: ₹{m.price or 'N/A'}, {req_rx}")

    return "\n".join(lines) + "\n"

def build_lab_tests_context(question: str, tests: list) -> str:
    """Matches user questions against lab test prerequisites."""
    nq = normalize_name(question)
    q_tokens = set(nq.split())
    if not q_tokens or not tests: return ""

    scored = []
    for t in tests:
        t_text = normalize_name(f"{t.name} {t.category or ''}")
        t_tokens = set(t_text.split())
        score = len(q_tokens & t_tokens)
        if score > 0:
            scored.append((score, t))

    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored: return ""

    lines = ["RELEVANT LAB TESTS:"]
    for _, t in scored[:5]:
        loc = "In-house" if t.is_inhouse else "External Partner"
        lines.append(f"- {t.name} ({t.category or 'General'}): Price: ₹{t.price or 'N/A'}, Turnaround: {t.turnaround_time or 'N/A'}, Location: {loc}")
        if t.prerequisites:
            lines.append(f"  Preparation/Prerequisites: {t.prerequisites}")

    return "\n".join(lines) + "\n"

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
    return """Respond in English only. 
CRITICAL RULE: Be extremely concise and conversational. Use 1 to 2 short sentences maximum. 
Do not write long paragraphs. Speak like a helpful receptionist on a quick phone call."""


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


def build_context(request: ChatRequest, db: Session, force_english: bool = False):
    hospital_id = request.hospital_id
    question = request.question
    today_str = datetime.now().strftime("%d-%m-%Y")
    prompt_date_str = datetime.now().strftime("%A, %B %d, %Y")

    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

# Fetch all structured data from the DB
    all_medicines = db.query(Medicine).filter(Medicine.hospital_id == hospital_id).all()
    all_tests = db.query(LabTest).filter(LabTest.hospital_id == hospital_id).all()

    # Build the context strings
    doctor_context, doctors_included = build_doctor_context(question, hospital_id, db)
    pharmacy_context = build_pharmacy_context(question, all_medicines)
    lab_tests_context = build_lab_tests_context(question, all_tests)

    embed_resp = client.embeddings.create(input=question, model="text-embedding-3-small")
    raw_results = (
        db.query(KnowledgeBase)
        .filter(KnowledgeBase.hospital_id == hospital_id)
        .order_by(KnowledgeBase.embedding.cosine_distance(embed_resp.data[0].embedding))
        .limit(3).all()
    )
    kb_context, chunks_included = build_kb_context(raw_results)

    lang_instruction = build_system_prompt_english()
    fallback_instruction = build_fallback_instruction(
    doctors_found=doctors_included,
    kb_chunks=chunks_included,
    has_pharmacy=len(all_medicines) > 0,
    has_labs=len(all_tests) > 0
)

    parts = [
        f"You are Arogya, the AI Assistant for {hospital.name}.",
        f"Current Date: {prompt_date_str}",
        "",
        hospital.system_prompt or "",
        "",
        lang_instruction,
        "",
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

    # Pick 2 real departments for specific questions
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

    ai_response = client.chat.completions.create(model=OPENAI_MODEL, messages=openai_messages)
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

# =============================================================================
# COMPLETE REPLACEMENT for the chat_stream endpoint and classify_user_intent
# in backend/app/api/v1/endpoints/ai.py
#
# Replace everything from:
#   async def classify_user_intent(...)
# through to the end of the file.
# =============================================================================
async def normalise_booking_input(
    raw_message: str,
    current_field: str,
    conversation_context: str = ""
) -> dict:
    """
    Uses the LLM to intelligently interpret and normalise a user's message
    in the context of what field is currently being collected.

    Returns a dict:
    {
        "intent": "provide" | "correct" | "cancel" | "unclear",
        "field_to_correct": "phone" | "name" | "age" | "date" | "time" | "doctor" | null,
        "normalised_value": "cleaned value ready to use" | null,
        "reason": "brief explanation if unclear or correction"
    }
    """
    system_prompt = f"""You are a data extraction assistant for a hospital booking system.

The assistant is currently collecting: {current_field}
Recent conversation:
{conversation_context}

The user just said: "{raw_message}"

Your job is to interpret what the user means and return a JSON object with these fields:
- "intent": one of "provide" (giving the requested info), "correct" (wants to change something already given), "cancel" (wants to stop entirely), "unclear" (genuinely ambiguous)
- "field_to_correct": if intent is "correct", which field they want to change. One of: phone, name, age, date, time, doctor. Otherwise null.
- "normalised_value": if intent is "provide", the cleaned value ready to use. For phone numbers, return only digits. For names, return only the name part (strip "and she is X years old" etc). For age, return only the number. Otherwise null.
- "reason": brief note if intent is "unclear" or "correct"

CRITICAL RULES for normalisation:
- Phone numbers: Convert spoken/spaced digits to a single string of digits. "94 67 48 74 48" → "9467487448". "nine four six seven..." → "9467487448". Remove all spaces, dashes, brackets.
- Names: Extract only the person's name. "Reetha and she is 50 years old" → "Reetha". "My name is John" → "John".
- Ages: Extract only the number. "I am 45 years old" → "45". "forty five" → "45".
- Corrections: "no my number is wrong" → intent=correct, field_to_correct=phone. "actually my name is..." → intent=correct, field_to_correct=name.
- True cancellations: "I don't want to book anymore" → intent=cancel. "stop everything" → intent=cancel.
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
        # Ensure all expected keys exist
        return {
            "intent": result.get("intent", "unclear"),
            "field_to_correct": result.get("field_to_correct"),
            "normalised_value": result.get("normalised_value"),
            "reason": result.get("reason", "")
        }
    except Exception as e:
        logger.warning("normalise_booking_input failed: %s", e)
        # Safe fallback: treat as a raw provide with the original message
        return {
            "intent": "provide",
            "field_to_correct": None,
            "normalised_value": raw_message,
            "reason": ""
        }
    
async def classify_user_intent(user_message: str, history: list = []) -> str:
    """
    Uses a fast LLM call to semantically classify the user's intent.
    Returns exactly one of: "STATUS", "BOOKING", "CANCEL", or "OTHER"
    
    This runs BEFORE build_context so we skip the expensive embedding
    call entirely when the user is booking or cancelling.
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
BOOKING - User wants to book/schedule an appointment, OR is providing booking details.
CANCEL  - User wants to cancel or stop an ongoing booking process.
OTHER   - General hospital questions, asking about medicines, lab tests, timings, or doctors.

RULES:
- If the user changes the subject to ask a general question (e.g., about medicines, lab tests, or where something is), output: OTHER (Even if you were in the middle of booking).
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
        # Defensive: only accept known intents
        return intent if intent in {"STATUS", "BOOKING", "CANCEL", "OTHER"} else "OTHER"
    except Exception as e:
        logger.warning("Intent classification failed: %s", e)
        return "OTHER"


@router.post("/chat-stream")
async def chat_stream(request: ChatRequest, db: Session = Depends(get_db)):
    is_malayalam = request.language == "ml"

    # Step 1: Translate input if Malayalam
    english_question = request.question
    if is_malayalam:
        english_question = await _translate_async(request.question, "ml", "en")
        logger.info("[Translation] ml->en: %r -> %r", request.question[:60], english_question[:60])

    # Step 2: Classify intent BEFORE any expensive DB/embedding calls
    intent = await classify_user_intent(english_question, request.history or [])
    logger.info("[Intent] %s -> %s", english_question[:60], intent)

    async def event_generator() -> AsyncGenerator[str, None]:
        pt = ct = tt = 0
        
        # ── CANCEL ───────────────────────────────────────────────────────────
        if intent == "CANCEL":
            msg = "Okay, I've cancelled any active requests. How else can I help you?"
            if is_malayalam:
                msg = await _translate_async(msg, "en", "ml")
            yield f"data: {json.dumps(msg)}\n\n"
            yield "data: [DONE]\n\n"
            return

        # ── STATUS CHECK ─────────────────────────────────────────────────────
        if intent == "STATUS":
            # Look for a phone number across current message + recent history
            history_text = " ".join(
                m.content for m in (request.history or [])[-6:]
            )
            combined = re.sub(r"[\s\-\(\)\.]", "", english_question + " " + history_text)
            phone_match = re.search(r"\+?\d{10,15}", combined)

            if not phone_match:
                msg = (
                    "I can check your appointment status! "
                    "Please share the 10-digit phone number you used when booking."
                )
                if is_malayalam:
                    msg = await _translate_async(msg, "en", "ml")
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
                    f"I couldn't find any appointments for the number {extracted_phone}. "
                    "Please double-check the number or contact the reception desk."
                )
                if is_malayalam:
                    msg = await _translate_async(msg, "en", "ml")
                yield f"data: {json.dumps(msg)}\n\n"
                yield "data: [DONE]\n\n"
                return

            reply_lines = ["Here is the status of your recent appointments:\n"]
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

        # ── BOOKING & GENERAL CHAT (BOOKING or OTHER) ─────────────────────────
        translated_request = request.model_copy(update={"question": english_question})
        system_prompt, openai_messages, hospital = build_context(
            translated_request, db, force_english=True
        )
        booking_field_keywords = {
            "phone": ["phone", "number", "mobile", "contact"],
            "name":  ["name", "patient's full name", "full name"],
            "age":   ["age", "how old", "date of birth"],
            "date":  ["date", "prefer", "which day"],
            "time":  ["morning", "afternoon", "evening", "time of day"],
            "doctor":["doctor", "which doctor", "department"],
        }
        current_field = None
        if request.history:
            last_assistant = next(
                (m.content.lower() for m in reversed(request.history) if m.role == "assistant"),
                ""
            )
            for field, keywords in booking_field_keywords.items():
                if any(kw in last_assistant for kw in keywords):
                    current_field = field
                    break

        processed_question = english_question
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
                msg = "Okay, I've cancelled the booking process. Is there anything else I can help you with?"
                if is_malayalam: msg = await _translate_async(msg, "en", "ml")
                yield f"data: {json.dumps(msg)}\n\n"
                yield "data: [DONE]\n\n"
                return

            if normalised["intent"] == "correct":
                field = normalised.get("field_to_correct", current_field)
                prompts = {
                    "phone":  "Of course! Please provide the correct phone number.",
                    "name":   "Of course! What is the correct patient name?",
                    "age":    "Of course! What is the correct age?",
                    "date":   "Of course! Which date would you prefer?",
                    "time":   "Of course! Morning, afternoon, or evening?",
                    "doctor": "Of course! Which doctor would you like to see?",
                }
                msg = prompts.get(field, "Of course! Please provide the correct information.")
                if is_malayalam: msg = await _translate_async(msg, "en", "ml")
                yield f"data: {json.dumps(msg)}\n\n"
                yield "data: [DONE]\n\n"
                return

            if normalised["intent"] == "provide" and normalised["normalised_value"]:
                processed_question = normalised["normalised_value"]
                openai_messages[-1]["content"] = processed_question

        # Agent instructions injected into the system prompt
        agent_instructions = """
APPOINTMENT BOOKING CAPABILITY:
You can book appointments for patients. Collect these details naturally, one at a time:
1. Doctor (use the [ID: X] from the doctor list above to identify them)
2. Preferred date (ask for a specific date like "April 20" or "next Monday")
3. Time of day (morning, afternoon, or evening)
4. Patient's full name (name only — do not accept extra words)
5. Patient's age (number only, 1-120)
6. Phone number (must be exactly 10 digits for Indian numbers)

VALIDATION RULES:
- Phone: exactly 10 digits (or up to 15 with country code). If wrong length, ask again.
- Name: extract only the name part; ignore extra words like "and she is 30 years old".
- Date: must be a future date.

IMPORTANT:
- Answer general questions normally using the knowledge base.
- Only trigger 'book_appointment' once you have confirmed ALL 6 details with the patient.
- Before triggering, show a confirmation summary and ask the patient to say 'yes' or 'no'.

- If they say no or want to change something, ask which detail to correct.
"""
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
                model=OPENAI_MODEL,
                messages=openai_messages,
                tools=tools,
                stream=True,
                stream_options={"include_usage": True}
            )
        except Exception as e:
            logger.exception("[chat-stream] OpenAI call failed: %s", e)
            err = "Sorry, I'm having trouble connecting right now. Please try again."
            if is_malayalam:
                err = await _translate_async(err, "en", "ml")
            yield f"data: {json.dumps(err)}\n\n"
            yield "data: [DONE]\n\n"
            return

        tool_call_name = ""
        tool_call_args = ""
        is_tool_call = False
        english_chunks: List[str] = []

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
                token = delta.content
                if is_malayalam:
                    english_chunks.append(token)
                else:
                    yield f"data: {json.dumps(token)}\n\n"

        # ── Handle tool call (booking) ────────────────────────────────────────
        if is_tool_call and tool_call_name == "book_appointment":
            try:
                from app.services.booking_rules import validate_booking, get_booking_config
                from app.services.email import notify_staff_new_appointment

                args = json.loads(tool_call_args)

                # Validate phone length
                phone_digits = re.sub(r"\D", "", args.get("patient_phone", ""))
                if len(phone_digits) < 7 or len(phone_digits) > 15:
                    err = (
                        f"The phone number '{args.get('patient_phone')}' doesn't look right. "
                        "Please ask the patient to provide their 10-digit mobile number again."
                    )
                    if is_malayalam:
                        err = await _translate_async(err, "en", "ml")
                    yield f"data: {json.dumps(err)}\n\n"
                    yield "data: [DONE]\n\n"
                    return

                # Validate age
                age_str = re.sub(r"\D", "", str(args.get("patient_age", "")))
                if not age_str or not (1 <= int(age_str) <= 120):
                    err = "The age doesn't look right. Please ask the patient to confirm their age."
                    if is_malayalam:
                        err = await _translate_async(err, "en", "ml")
                    yield f"data: {json.dumps(err)}\n\n"
                    yield "data: [DONE]\n\n"
                    return

                doctor = db.query(Doctor).filter(
                    Doctor.id == args["doctor_id"],
                    Doctor.hospital_id == request.hospital_id
                ).first()

                if not doctor:
                    err = (
                        "I couldn't find that doctor in the system. "
                        "Please ask the patient which doctor they'd like to see."
                    )
                    if is_malayalam:
                        err = await _translate_async(err, "en", "ml")
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
                db.add(appt)
                db.commit()
                db.refresh(appt)

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

                success_msg = (
                    f"✅ **Appointment Request Submitted!**\n\n"
                    f"Reference: **{appt.reference_number}**\n"
                    f"Doctor: {doctor.name} ({doctor.department})\n"
                    f"Date: {appt.preferred_date} — {appt.time_of_day.title()}\n"
                    f"Patient: {appt.patient_name}, age {appt.patient_age}\n\n"
                    f"The hospital will call **{appt.patient_phone}** to confirm your slot."
                )
                if is_malayalam:
                    success_msg = await _translate_async(success_msg, "en", "ml")
                yield f"data: {json.dumps(success_msg)}\n\n"
                yield "data: [DONE]\n\n"  # ← add this
                return   

            except json.JSONDecodeError:
                logger.error("[chat-stream] Failed to parse tool args: %r", tool_call_args)
                err = "Something went wrong while booking. Please try again."
                if is_malayalam:
                    err = await _translate_async(err, "en", "ml")
                yield f"data: {json.dumps(err)}\n\n"
            except Exception as e:
                logger.exception("[chat-stream] Tool execution error: %s", e)
                err = "Sorry, there was a technical error. Please try again."
                if is_malayalam:
                    err = await _translate_async(err, "en", "ml")
                yield f"data: {json.dumps(err)}\n\n"

        else:
            # Normal chat response — translate if needed
            if is_malayalam and english_chunks:
                full_english = "".join(english_chunks)
                full_malayalam = await _translate_async(full_english, "en", "ml")
                sentences = re.split(r'(?<=[.!?।\n])\s*', full_malayalam)
                for sentence in sentences:
                    if sentence.strip():
                        yield f"data: {json.dumps(sentence + ' ')}\n\n"

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
        # 1. Save audio temporarily
        with open(temp_filename, "wb") as buffer:
            buffer.write(await file.read())

        # 2. Reject clips that are too short — causes hallucinations
        file_size = os.path.getsize(temp_filename)
        duration_seconds = file_size / (16000 * 2)  # 16kHz 16-bit mono
        if duration_seconds < 1.0:
            return {"transcript": ""}
        if duration_seconds > 28.0:  # Sarvam limit is 30s, give 2s buffer
            return {"transcript": ""}

        # 3. Pick the right model and language code
        if language == "ml":
            # saaras:v3 with codemix mode = Malayalam script + English words in English
            # This is exactly what you need for "ഇന്ന് pediatrician ഉണ്ടോ?"
            model = "saaras:v3"
            lang_code = "ml-IN"
            mode = "codemix"
        else:
            model = "saarika:v2.5"
            lang_code = "en-IN"
            mode = "transcribe"

        # 4. Send to Sarvam
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