import os
import re
import json
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
from app.core.config import settings
from app.api.deps import get_db, get_current_tenant, get_token_payload
from app.models.hospital import Hospital
from app.services.security import detect_prompt_injection
# NOTE: _translate (sync) confirmed unused as of 2026-08-02 — zero call sites
# in this file or the rest of the repo (only _translate_async is used).
# TODO: Remove in future cleanup task alongside _session_key and resolve_doctor_id.
from app.services.translation import _translate, _translate_async
from app.services.vocabulary import (
    _DEPT_SYNONYMS,
    _expand_with_synonyms,
    normalize_name,
    score_doctor_relevance,
)
from app.services.patient_context import (
    PATIENT_CTX_TTL,
    _patient_ctx_key,
    _load_patient_ctx,
    _save_patient_ctx,
    _update_patient_ctx,
    _build_patient_ctx_block,
    _log_task_completion,
)
from app.services.rag import (
    build_context,
    build_history_messages,
    extract_text_from_pdf,
    chunk_text,
    embed_chunks_batch,
)
from app.services.booking import (
    _RELEVANCE_STAGES,
    _reset_relevance_gate,
    _is_new_booking_attempt,
    normalise_booking_input,
    classify_user_intent,
)
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
QUESTION_MIN_LENGTH      = 1
QUESTION_MAX_LENGTH      = 500
VALID_LANGUAGES          = {"en", "ml"}


# =============================================================================
# PATIENT CONTEXT + VOCABULARY — moved to services
# =============================================================================
# PATIENT_CTX_TTL, _patient_ctx_key, _load_patient_ctx, _save_patient_ctx,
# _update_patient_ctx, _build_patient_ctx_block, _log_task_completion
#   → app.services.patient_context
# _DEPT_SYNONYMS, _expand_with_synonyms, normalize_name, score_doctor_relevance
#   → app.services.vocabulary
# All imported at the top of this file; call sites below are unchanged.

# =============================================================================
# FEATURE 4 — RELEVANCE GATE HELPERS
# =============================================================================
# _RELEVANCE_STAGES, _reset_relevance_gate, _is_new_booking_attempt
#   → app.services.booking
# All imported at the top of this file; call sites below are unchanged.

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
# _DEPT_SYNONYMS, _expand_with_synonyms, normalize_name, score_doctor_relevance
# moved to app.services.vocabulary — imported at top of this file.


# =============================================================================
# RAG PIPELINE — moved to app.services.rag
# =============================================================================
# check_doctor_availability_db, build_doctor_context, build_pharmacy_context,
# build_lab_tests_context, build_kb_context, build_system_prompt_english,
# build_system_prompt_malayalam, build_fallback_instruction, build_context,
# build_history_messages, extract_text_from_pdf, chunk_text, embed_chunks_batch
# All imported at the top of this file.


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

    # Custom Welcome Message Logic
    if hospital.welcome_message and hospital.welcome_message.strip():
        base_en_greeting = hospital.welcome_message.strip()
        try:
            base_ml_greeting = await _translate_async(base_en_greeting, source="en", target="ml")
        except Exception:
            # Fallback: Just show the English text rather than awkwardly mixing two languages in one sentence
            base_ml_greeting = f"{base_en_greeting}"
    else:
        base_en_greeting = f"Hello! I am **Arogya**, the AI assistant for **{hospital_name}**."
        base_ml_greeting = f"നമസ്കാരം! ഞാൻ **ആരോഗ്യ**, **{hospital_name}**-ന്റെ AI അസിസ്റ്റന്റ്."

    en_msg = "\n".join([
        f"### 👋 {base_en_greeting}",
        "",
        "Here is what I can help you with:",
        *[f"- {c}" for c in en_caps],
        "",
        "Type or tap the mic to speak 🎤",
    ])

    ml_msg = "\n".join([
        f"### 👋 {base_ml_greeting}",
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
# normalise_booking_input, classify_user_intent
#   → app.services.booking
# All imported at the top of this file; call sites below are unchanged.


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
async def update_knowledge_entry(entry_id: int, request: UpdateKnowledgeRequest, db: Session = Depends(get_db), _tenant: int = Depends(get_current_tenant), token_data: dict = Depends(get_token_payload)):
    entry = db.query(KnowledgeBase).filter(KnowledgeBase.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")

    user_role = token_data.get("role")
    user_hospital = token_data.get("hospital_id")
    if user_role != "superadmin" and str(user_hospital) != str(entry.hospital_id):
        raise HTTPException(status_code=403, detail="Not authorized to modify this resource")

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
async def delete_knowledge_entry(entry_id: int, db: Session = Depends(get_db), _tenant: int = Depends(get_current_tenant), token_data: dict = Depends(get_token_payload)):
    entry = db.query(KnowledgeBase).filter(KnowledgeBase.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")

    user_role = token_data.get("role")
    user_hospital = token_data.get("hospital_id")
    if user_role != "superadmin" and str(user_hospital) != str(entry.hospital_id):
        raise HTTPException(status_code=403, detail="Not authorized to modify this resource")

    try:
        db.delete(entry)
        db.commit()
        return {"status": "success", "message": "Entry deleted"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))