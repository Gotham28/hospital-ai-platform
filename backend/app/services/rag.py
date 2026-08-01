"""
services/rag.py
───────────────
RAG (Retrieval-Augmented Generation) pipeline — all context-building,
system-prompt assembly, and PDF/ingest helpers.

Extracted from app.api.v1.endpoints.ai — Stage 4 of service extraction.

Public API
----------
check_doctor_availability_db(doctor, db, target_date) -> str
build_doctor_context(question, hospital_id, db) -> tuple[str, int]
build_pharmacy_context(question, medicines) -> str
build_lab_tests_context(question, tests) -> str
build_kb_context(results) -> tuple[str, int]
build_system_prompt_english() -> str
build_system_prompt_malayalam() -> str
build_fallback_instruction(doctors_found, kb_chunks, has_pharmacy, has_labs) -> str
build_history_messages(history) -> list[dict]
build_context(request, db, force_english, session_token) -> tuple[str, list, Hospital]
extract_text_from_pdf(pdf_bytes) -> tuple[str, int]
chunk_text(text) -> list[str]
embed_chunks_batch(chunks) -> list[list[float]]

Design rules
------------
- No circular imports: this module must NOT import from ai.py.
- The OpenAI client is constructed once at module load, same pattern as ai.py.
- All DB queries are tenant-scoped (hospital_id filter mandatory).
- build_context is the "heavy" orchestrator — call everything else first.
"""
import logging
import os
import re
from datetime import datetime
from typing import List

import fitz  # PyMuPDF
from fastapi import HTTPException
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import OpenAI
from sqlalchemy.orm import Session

from app.models.doctor import Doctor
from app.models.doctor_availability import DoctorSchedule, DoctorLeave
from app.models.hospital import Hospital
from app.models.knowledge import KnowledgeBase
from app.models.lab_test import LabTest
from app.models.medicine import Medicine
from app.services.patient_context import _load_patient_ctx, _build_patient_ctx_block
from app.services.vocabulary import normalize_name

logger = logging.getLogger(__name__)

# =============================================================================
# OPENAI CLIENT
# =============================================================================
# Constructed once at import time, same pattern as ai.py.
_api_key = os.getenv("OPENAI_API_KEY")
if not _api_key:
    raise RuntimeError("OPENAI_API_KEY environment variable is not set.")
client = OpenAI(api_key=_api_key)

# =============================================================================
# CONSTANTS OWNED BY THIS MODULE
# =============================================================================
PDF_CHUNK_SIZE           = 800
PDF_CHUNK_OVERLAP        = 100
DOCTOR_SECTION_MAX_CHARS = 2_400
KB_CHUNK_MAX_CHARS       = 500
KB_SECTION_MAX_CHARS     = 1_500
MAX_RELEVANT_DOCTORS     = 15
DEFAULT_DOCTORS_IF_NO_MATCH = 5
SYSTEM_PROMPT_WARN_CHARS = 12_000


# =============================================================================
# DOCTOR AVAILABILITY
# =============================================================================

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


# =============================================================================
# DOCTOR CONTEXT BUILDER
# =============================================================================

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


# =============================================================================
# PHARMACY CONTEXT BUILDER
# =============================================================================

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


# =============================================================================
# LAB TESTS CONTEXT BUILDER
# =============================================================================

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


# =============================================================================
# KB CONTEXT BUILDER
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
# SYSTEM PROMPT BUILDERS
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

Answer confidently from this data. If asked about something genuinely outside this data \
(specific room numbers, exact wait times, billing disputes), acknowledge you don't have \
that specific detail and suggest calling reception. Never refuse to answer about doctors, \
departments, or services that appear in your context above."""


# =============================================================================
# HISTORY MESSAGES
# =============================================================================

def build_history_messages(history) -> List[dict]:
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
# BUILD CONTEXT — main orchestrator (call last)
# =============================================================================

def build_context(
    request,
    db: Session,
    force_english: bool = False,
    session_token: str = "default",
):
    """
    Build the full system prompt + OpenAI messages list for a chat turn.

    Parameters
    ----------
    request : ChatRequest
        The incoming chat request (typed as Any to avoid circular import).
    db : Session
        SQLAlchemy session, already scoped to this request.
    force_english : bool
        If True, use the English system prompt regardless of request.language.
    session_token : str
        Redis session key for patient context lookup.

    Returns
    -------
    (system_prompt, openai_messages, hospital)
    """
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

    # ── Patient personalisation block ─────────────────────────────────────
    patient_ctx       = _load_patient_ctx(hospital_id, session_token)
    patient_ctx_block = _build_patient_ctx_block(patient_ctx)

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
        patient_ctx_block,          # injected before doctor context
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
# PDF / INGEST HELPERS
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
