import os
import re
import json
import fitz
import logging
import unicodedata
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

logger = logging.getLogger(__name__)
router = APIRouter()

_api_key = os.getenv("OPENAI_API_KEY")
if not _api_key:
    raise RuntimeError("OPENAI_API_KEY environment variable is not set.")

client = OpenAI(api_key=_api_key)
async_client = AsyncOpenAI(api_key=_api_key)

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
            return (
                "Your message contains patterns that cannot be processed. "
                "Please ask a straightforward question about doctors, timings, or services."
            )
    return None

def sanitise_question(text: str) -> str:
    text = re.sub(r"\s+", " ", text.strip())
    text = unicodedata.normalize("NFKC", text)
    return text


# =============================================================================
# MODELS
# =============================================================================

class IngestRequest(BaseModel):
    hospital_id: int
    text: str

    @field_validator("hospital_id")
    @classmethod
    def hospital_id_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("hospital_id must be a positive integer")
        return v

    @field_validator("text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text must not be empty or whitespace only")
        return v


class HistoryMessage(BaseModel):
    role: str
    content: str

    @field_validator("role")
    @classmethod
    def role_valid(cls, v: str) -> str:
        if v not in ("user", "assistant"):
            raise ValueError("role must be 'user' or 'assistant'")
        return v

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("content must not be empty")
        return v.strip()


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=QUESTION_MIN_LENGTH, max_length=QUESTION_MAX_LENGTH)
    hospital_id: int = Field(..., gt=0)
    language: str = Field(default="en")
    history: Optional[List[HistoryMessage]] = Field(default_factory=list)

    @field_validator("language")
    @classmethod
    def language_valid(cls, v: str) -> str:
        n = v.strip().lower()
        if n not in VALID_LANGUAGES:
            raise ValueError(f"language must be one of {sorted(VALID_LANGUAGES)}")
        return n

    @field_validator("question")
    @classmethod
    def question_not_whitespace(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("question must contain at least one non-whitespace character")
        return v

    @model_validator(mode="after")
    def check_injection_and_sanitise(self) -> "ChatRequest":
        sanitised = sanitise_question(self.question)
        reason = detect_prompt_injection(sanitised)
        if reason:
            logger.warning(
                "Prompt injection attempt for hospital_id=%s: %.100s",
                self.hospital_id, self.question,
            )
            raise ValueError(reason)
        self.question = sanitised
        return self


# =============================================================================
# DOCTOR RELEVANCE FILTERING
# =============================================================================

def normalize_name(text: str) -> str:
    text = text.lower()
    text = re.sub(r"dr\.?", "", text)
    text = re.sub(r"[^a-z\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()


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


def score_doctor_relevance(question: str, doctor: Doctor) -> float:
    q_tokens = set(normalize_name(question).split())
    if not q_tokens:
        return 0.0
    d_text = " ".join(filter(None, [doctor.name or "", doctor.department or "", doctor.base_schedule or ""]))
    d_tokens = set(normalize_name(d_text).split())
    return len(q_tokens & d_tokens) / len(q_tokens) if d_tokens else 0.0


def build_doctor_context(question: str, doctors: List[Doctor]) -> tuple[str, int]:
    if not doctors:
        return "No doctors currently registered for this hospital.\n", 0
    scored = sorted([(score_doctor_relevance(question, d), d) for d in doctors], key=lambda x: x[0], reverse=True)
    top_score = scored[0][0] if scored else 0.0
    limit = MAX_RELEVANT_DOCTORS if top_score > 0.05 else DEFAULT_DOCTORS_IF_NO_MATCH
    lines, total_chars, truncated = [], 0, False
    for _, doctor in scored[:limit]:
        line = f"- {doctor.name} ({doctor.department or 'General'}): Schedule {doctor.base_schedule or 'Not specified'}\n"
        if total_chars + len(line) > DOCTOR_SECTION_MAX_CHARS:
            truncated = True
            break
        lines.append(line)
        total_chars += len(line)
    section = "RELEVANT DOCTORS FOR THIS QUERY:\n" + "".join(lines)
    if truncated:
        section += f"(List truncated. Total doctors on file: {len(doctors)})\n"
    return section, len(lines)


# =============================================================================
# KB CONTEXT
# =============================================================================

def build_kb_context(chunks: list) -> tuple[str, int]:
    if not chunks:
        return "", 0
    trimmed, total = [], 0
    for chunk in chunks:
        text = chunk.content.strip()
        if len(text) > KB_CHUNK_MAX_CHARS:
            text = text[:KB_CHUNK_MAX_CHARS].rsplit(" ", 1)[0] + "…"
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
    except AvailabilityError as e:
        logger.error("[Availability] Fetch failed hospital_id=%s sheet_id=%s: %s", hospital_id, sheet_id, e)
        stale = get_cached_or_empty(sheet_id)
        if stale:
            doc_id, doc_name = resolve_doctor_id(question, stale)
            if doc_id:
                doc_info = stale.get(doc_id, {})
                absent = [d.strip() for d in str(doc_info.get("absent_dates", "")).split(",") if d.strip()]
                qualifier = "ABSENT" if today_str in absent else "available"
                return (f"AVAILABILITY DATA (may be up to 5 minutes old): "
                        f"{doc_name} was marked {qualifier} for today ({today_str}). "
                        "Advise the patient to confirm by calling reception.")
        return ("SYSTEM NOTE: Live doctor availability data is currently unreachable. "
                "You MUST NOT guess whether any doctor is available. "
                "Tell the patient to call the hospital reception directly.")
    except Exception as e:
        logger.exception("[Availability] Unexpected error hospital_id=%s: %s", hospital_id, e)
        return ("SYSTEM NOTE: Live availability unreachable. "
                "You MUST NOT guess availability. Ask the patient to call reception.")


# =============================================================================
# SYSTEM PROMPT BUILDER
# =============================================================================

def build_malayalam_instruction(lang: str) -> str:
    """
    FIX: The original prompt had a contradiction:
      - lang_instruction said: 'Respond ONLY in Malayalam script. Do NOT use English script.'
      - behavior_guidelines said: 'Use Manglish style — English terms written in Malayalam script.'

    'Do NOT use English script' told the model to avoid the Latin alphabet entirely.
    'Manglish' requires mixing Malayalam script with English-origin words
    (e.g. 'Cardiology' stays as 'കാർഡിയോളജി', which IS Malayalam script
    but is an English loanword — this is fine and correct).

    The real instruction the model needs:
      - Write in Malayalam script (not Latin alphabet)
      - Medical/technical terms that are English loanwords should be
        transliterated into Malayalam script, NOT translated literally
      - When the answer is not in context, say so in Malayalam, do not guess
    """
    if lang != "ml":
        return "Respond in English only."

    return """LANGUAGE: Respond entirely in Malayalam script (മലയാളം).

STYLE RULES for Malayalam responses:
1. Medical and technical terms that are English loanwords should be written
   in Malayalam script as they are pronounced — do NOT invent pure Malayalam
   translations for them.
   CORRECT: കാർഡിയോളജി (Cardiology), ഫാർമസി (Pharmacy), ഓർത്തോപീഡിക്സ് (Orthopaedics)
   WRONG:   ഹൃദ്രോഗ ശാസ്ത്രം (invented pure Malayalam — sounds unnatural and confusing)

2. Doctor names, department names, and proper nouns: write them in Malayalam
   script exactly as they are pronounced in spoken Malayalam.

3. Tone: Like a friendly, professional hospital receptionist speaking to a patient.
   Warm, clear, and direct.

4. Length: Give complete answers. Do not cut a sentence short.
   If listing doctors, list all that are relevant."""


def build_fallback_instruction() -> str:
    """
    Explicit do-not-guess guardrail placed at the END of the system prompt
    where it has the strongest recency effect on the model.
    """
    return """IMPORTANT — WHEN YOU DO NOT KNOW SOMETHING:
If the patient asks about something not mentioned in the doctor list or knowledge
above (e.g. pharmacy location, visiting hours, room numbers, fees) and you do not
have that information:
- English: Say clearly: "I don't have that information. Please ask at the reception desk."
- Malayalam: Say: "എനിക്ക് ആ വിവരം ലഭ്യമല്ല. ദയവായി റിസപ്ഷൻ ഡെസ്കിൽ ചോദിക്കൂ."

Do NOT make up answers. Do NOT say information that is not in your context above."""


def build_context(request: ChatRequest, db: Session):
    hospital_id = request.hospital_id
    question = request.question
    target_lang = request.language
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

    lang_instruction = build_malayalam_instruction(target_lang)
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

    # Fallback instruction at the end — highest recency weight
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

@router.get("/suggestions/{hospital_id}")
async def get_suggestions(hospital_id: int, db: Session = Depends(get_db)):
    """
    Returns dynamic suggestion chips for the chat UI, based on what the
    hospital has actually configured — doctors and KB content.

    This replaces the hardcoded suggestions in Chat.tsx that pointed to
    pharmacy locations and cardiologists the bot may know nothing about.

    Response:
    {
      "en": ["Which doctors are available today?", ...],
      "ml": ["ഇന്ന് ഏത് ഡോക്ടർ ഉണ്ട്?", ...]
    }
    """
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    doctors = db.query(Doctor).filter(Doctor.hospital_id == hospital_id).limit(3).all()
    has_kb = db.query(KnowledgeBase).filter(KnowledgeBase.hospital_id == hospital_id).first() is not None

    en_suggestions = []
    ml_suggestions = []

    # Doctor-based suggestions — only shown if doctors are registered
    if doctors:
        # Show up to 2 department-specific suggestions
        for doctor in doctors[:2]:
            dept = doctor.department or "General"
            en_suggestions.append(f"Who is the {dept} doctor?")
            ml_suggestions.append(f"{dept} ഡോക്ടർ ആരാണ്?")

        en_suggestions.append("Which doctors are available today?")
        ml_suggestions.append("ഇന്ന് ഏത് ഡോക്ടർ ഉണ്ട്?")
    else:
        # No doctors yet — safe generic prompts
        en_suggestions.append("What can Arogya help me with?")
        ml_suggestions.append("ആരോഗ്യ എന്തൊക്കെ സഹായിക്കും?")

    # KB-based suggestions — only shown if KB has content
    if has_kb:
        en_suggestions.append("What are the hospital timings?")
        ml_suggestions.append("ആശുപത്രി സമയം എന്താണ്?")
    else:
        en_suggestions.append("How do I contact the hospital?")
        ml_suggestions.append("ആശുപത്രിയിൽ എങ്ങനെ ബന്ധപ്പെടാം?")

    # Always-safe last suggestion
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
        "message": f"'{file.filename}' → {len(chunks)} chunks stored for {hospital.name}."
    }


@router.post("/chat")
async def chat_with_arogya(request: ChatRequest, db: Session = Depends(get_db)):
    _, openai_messages, _ = build_context(request, db)
    ai_response = client.chat.completions.create(model="gpt-4o-mini", messages=openai_messages)
    usage = ai_response.usage
    db.add(UsageLedger(
        hospital_id=request.hospital_id, endpoint="/chat",
        prompt_tokens=usage.prompt_tokens, completion_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens, estimated_cost=(usage.total_tokens / 1_000_000) * 0.15
    ))
    db.commit()
    return {"answer": ai_response.choices[0].message.content}


@router.post("/chat-stream")
async def chat_stream(request: ChatRequest, db: Session = Depends(get_db)):
    _, openai_messages, _ = build_context(request, db)

    async def event_generator() -> AsyncGenerator[str, None]:
        pt = ct = tt = 0
        try:
            stream = await async_client.chat.completions.create(
                model="gpt-4o-mini", messages=openai_messages,
                stream=True, stream_options={"include_usage": True}
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                token = delta.content if delta and delta.content else None
                if token:
                    yield f"data: {json.dumps(token)}\n\n"
                if chunk.usage:
                    pt, ct, tt = chunk.usage.prompt_tokens, chunk.usage.completion_tokens, chunk.usage.total_tokens
            yield "data: [DONE]\n\n"
            if tt > 0:
                db.add(UsageLedger(
                    hospital_id=request.hospital_id, endpoint="/chat-stream",
                    prompt_tokens=pt, completion_tokens=ct, total_tokens=tt,
                    estimated_cost=(tt / 1_000_000) * 0.15
                ))
                db.commit()
        except Exception as e:
            yield f"data: [ERROR] {str(e)}\n\n"

    return StreamingResponse(
        event_generator(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"}
    )