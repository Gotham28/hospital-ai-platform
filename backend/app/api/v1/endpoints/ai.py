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
# GOOGLE TRANSLATE BRIDGE
# =============================================================================
# Uses the free Google Translate endpoint (no API key needed).
# This is the same endpoint the browser uses — it's reliable for Malayalam.
# If it ever fails, we fall through gracefully (English answer is returned).

_GTRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"

def _translate(text: str, source: str, target: str) -> str:
    """
    Translate text using the free Google Translate endpoint.
    Returns the original text unchanged if translation fails.
    """
    if not text or not text.strip():
        return text
    try:
        params = {
            "client": "gtx",
            "sl": source,
            "tl": target,
            "dt": "t",
            "q": text,
        }
        resp = httpx.get(_GTRANSLATE_URL, params=params, timeout=8.0)
        resp.raise_for_status()
        data = resp.json()
        # Response structure: [[[translated, original, ...], ...], ...]
        translated_parts = [part[0] for part in data[0] if part[0]]
        return "".join(translated_parts)
    except Exception as e:
        logger.warning("Translation failed (%s→%s): %s", source, target, e)
        return text  # Fall back to untranslated text


async def _translate_async(text: str, source: str, target: str) -> str:
    """
    Async version of _translate for use in streaming endpoint.
    """
    if not text or not text.strip():
        return text
    try:
        params = {
            "client": "gtx",
            "sl": source,
            "tl": target,
            "dt": "t",
            "q": text,
        }
        async with httpx.AsyncClient() as http:
            resp = await http.get(_GTRANSLATE_URL, params=params, timeout=8.0)
            resp.raise_for_status()
            data = resp.json()
            translated_parts = [part[0] for part in data[0] if part[0]]
            return "".join(translated_parts)
    except Exception as e:
        logger.warning("Async translation failed (%s→%s): %s", source, target, e)
        return text


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
# DOCTOR CONTEXT
# =============================================================================

def build_doctor_context(question: str, all_doctors: list) -> tuple[str, int]:
    if not all_doctors:
        return "DOCTORS: No doctors are currently registered for this hospital.", 0

    q_lower = question.lower()
    scored = []
    for doc in all_doctors:
        score = 0
        dept = (doc.department or "").lower()
        name = (doc.name or "").lower()
        if dept and dept in q_lower:
            score += 3
        if name and any(word in q_lower for word in name.split() if len(word) > 2):
            score += 2
        scored.append((score, doc))

    scored.sort(key=lambda x: -x[0])
    top_scored = [d for s, d in scored if s > 0][:MAX_RELEVANT_DOCTORS]
    if not top_scored:
        top_scored = [d for _, d in scored[:DEFAULT_DOCTORS_IF_NO_MATCH]]

    lines = ["DOCTORS AT THIS HOSPITAL:"]
    total_chars = len(lines[0])
    included = 0

    for doc in top_scored:
        schedule = doc.schedule or "Schedule not specified"
        line = f"- {doc.name} ({doc.department or 'General'}): {schedule}"
        if total_chars + len(line) > DOCTOR_SECTION_MAX_CHARS:
            break
        lines.append(line)
        total_chars += len(line)
        included += 1

    return "\n".join(lines), included


def build_kb_context(results: list) -> tuple[str, int]:
    if not results:
        return "", 0
    chunks = []
    total_chars = 0
    for row in results:
        text = (row.content or "").strip()
        if not text:
            continue
        snippet = text[:KB_CHUNK_MAX_CHARS]
        if total_chars + len(snippet) > KB_SECTION_MAX_CHARS:
            break
        chunks.append(snippet)
        total_chars += len(snippet)
    return "\n---\n".join(chunks), len(chunks)


# =============================================================================
# AVAILABILITY
# =============================================================================

def fetch_availability_context(question: str, sheet_id: str, hospital_id: int, today_str: str) -> str:
    try:
        avail = get_cached_or_empty(hospital_id)
        if not avail:
            return ""
        q_lower = question.lower()
        for doc_name, info in avail.items():
            if doc_name.lower() in q_lower or any(w in q_lower for w in doc_name.lower().split() if len(w) > 3):
                qualifier = "available" if info.get("available") else "unavailable"
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

def build_system_prompt_english() -> str:
    """
    When using the translation bridge, the LLM always reasons in English.
    This prompt is clean, English-only, focused on accuracy.
    """
    return "Respond in English only. Be clear, accurate, and concise."


def build_fallback_instruction() -> str:
    return """IMPORTANT — WHEN YOU DO NOT KNOW SOMETHING:
If the patient asks about something not mentioned in the doctor list or knowledge
above (e.g. pharmacy location, visiting hours, room numbers, fees) and you do not
have that information:
- Say clearly: "I don't have that information. Please ask at the reception desk."

Do NOT make up answers. Do NOT say information that is not in your context above."""


def build_context(request: ChatRequest, db: Session, force_english: bool = False):
    """
    Build the system prompt and OpenAI messages.

    When force_english=True (used by the translation bridge), the question
    passed in is already translated to English, and we use an English-only
    system prompt so the LLM never attempts to output Malayalam itself.
    """
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

    # Always use English instructions when translation bridge is active
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

@router.get("/suggestions/{hospital_id}")
async def get_suggestions(hospital_id: int, db: Session = Depends(get_db)):
    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    doctors = db.query(Doctor).filter(Doctor.hospital_id == hospital_id).limit(3).all()
    has_kb = db.query(KnowledgeBase).filter(KnowledgeBase.hospital_id == hospital_id).first() is not None

    en_suggestions = []
    ml_suggestions = []

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
        "message": f"'{file.filename}' → {len(chunks)} chunks stored for {hospital.name}."
    }


@router.post("/chat")
async def chat_with_arogya(request: ChatRequest, db: Session = Depends(get_db)):
    is_malayalam = request.language == "ml"

    # ── Translation bridge: Malayalam → English ───────────────────────────────
    english_question = request.question
    if is_malayalam:
        english_question = _translate(request.question, source="ml", target="en")
        logger.info("[Translation] ml→en: %r → %r", request.question[:80], english_question[:80])

    # Build context using the English question so RAG/embedding works correctly
    translated_request = request.model_copy(update={"question": english_question})
    _, openai_messages, _ = build_context(translated_request, db, force_english=True)

    ai_response = client.chat.completions.create(model="gpt-4o-mini", messages=openai_messages)
    english_answer = ai_response.choices[0].message.content or ""

    # ── Translation bridge: English → Malayalam ───────────────────────────────
    final_answer = english_answer
    if is_malayalam:
        final_answer = _translate(english_answer, source="en", target="ml")
        logger.info("[Translation] en→ml answer preview: %r", final_answer[:80])

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

    # ── Translation bridge: Malayalam → English ───────────────────────────────
    english_question = request.question
    if is_malayalam:
        english_question = await _translate_async(request.question, source="ml", target="en")
        logger.info("[Translation] ml→en: %r → %r", request.question[:80], english_question[:80])

    translated_request = request.model_copy(update={"question": english_question})
    _, openai_messages, _ = build_context(translated_request, db, force_english=True)

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
                        # Buffer tokens — we translate the full answer at the end
                        english_chunks.append(token)
                    else:
                        # English: stream tokens directly as before
                        yield f"data: {json.dumps(token)}\n\n"
                if chunk.usage:
                    pt, ct, tt = chunk.usage.prompt_tokens, chunk.usage.completion_tokens, chunk.usage.total_tokens

            # ── Translation bridge: translate full English response → Malayalam ──
            if is_malayalam and english_chunks:
                full_english = "".join(english_chunks)
                logger.info("[Translation] en→ml full response (%d chars)", len(full_english))
                full_malayalam = await _translate_async(full_english, source="en", target="ml")

                # Stream the Malayalam response in sentence-sized chunks so
                # the frontend typing cursor still animates naturally
                import re as _re
                sentences = _re.split(r'(?<=[.!?।\n])\s*', full_malayalam)
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