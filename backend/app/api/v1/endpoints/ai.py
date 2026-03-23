import os
import re
import json
import fitz  # PyMuPDF
import logging
from typing import List, Optional, AsyncGenerator
from datetime import datetime
from pydantic import BaseModel, Field
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

MAX_HISTORY_TURNS = 10
PDF_CHUNK_SIZE = 800
PDF_CHUNK_OVERLAP = 100

DOCTOR_SECTION_MAX_CHARS    = 2_400
KB_CHUNK_MAX_CHARS          = 500
KB_SECTION_MAX_CHARS        = 1_500
MAX_RELEVANT_DOCTORS        = 15
DEFAULT_DOCTORS_IF_NO_MATCH = 5
SYSTEM_PROMPT_WARN_CHARS    = 12_000


# =============================================================================
# MODELS
# =============================================================================

class IngestRequest(BaseModel):
    hospital_id: int
    text: str


class HistoryMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    question: str
    hospital_id: int
    language: Optional[str] = "en"
    history: Optional[List[HistoryMessage]] = Field(default_factory=list)


# =============================================================================
# DOCTOR RELEVANCE FILTERING
# =============================================================================

def normalize_name(text: str) -> str:
    text = text.lower()
    text = re.sub(r"dr\.?", "", text)
    text = re.sub(r"[^a-z\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def resolve_doctor_id(user_text: str, doctor_data: dict):
    """Fuzzy-match a doctor name mentioned in the user's question."""
    normalized_query = normalize_name(user_text)
    best_match, best_score = None, 0

    for doctor_id, d in doctor_data.items():
        name = d.get("name", "") if isinstance(d, dict) else str(d)
        norm_name = normalize_name(name)
        query_tokens = set(normalized_query.split())
        name_tokens = set(norm_name.split())
        if not query_tokens or not name_tokens:
            continue
        score = len(query_tokens & name_tokens) / len(name_tokens)
        if score > best_score:
            best_score = score
            best_match = (doctor_id, name)

    return best_match if best_score >= 0.5 else (None, None)


def score_doctor_relevance(question: str, doctor: Doctor) -> float:
    """Score how relevant a doctor record is to the patient's question."""
    q_norm = normalize_name(question)
    q_tokens = set(q_norm.split())
    if not q_tokens:
        return 0.0

    doctor_text = " ".join(filter(None, [
        doctor.name or "",
        doctor.department or "",
        doctor.base_schedule or "",
        doctor.doctor_id or "",
    ]))
    d_norm = normalize_name(doctor_text)
    d_tokens = set(d_norm.split())

    if not d_tokens:
        return 0.0

    return len(q_tokens & d_tokens) / len(q_tokens)


def build_doctor_context(question: str, doctors: List[Doctor]) -> tuple[str, int]:
    """Relevance-filter and budget-cap the doctor directory section."""
    if not doctors:
        return "No doctors currently registered for this hospital.\n", 0

    scored = sorted(
        [(score_doctor_relevance(question, d), d) for d in doctors],
        key=lambda x: x[0],
        reverse=True,
    )

    top_score = scored[0][0] if scored else 0.0
    limit = MAX_RELEVANT_DOCTORS if top_score > 0.05 else DEFAULT_DOCTORS_IF_NO_MATCH
    selected = [d for _, d in scored[:limit]]

    lines = []
    total_chars = 0
    truncated = False

    for doctor in selected:
        line = (
            f"- {doctor.name}"
            f" ({doctor.department or 'General'})"
            f": Schedule {doctor.base_schedule or 'Not specified'}\n"
        )
        if total_chars + len(line) > DOCTOR_SECTION_MAX_CHARS:
            truncated = True
            break
        lines.append(line)
        total_chars += len(line)

    section = "RELEVANT DOCTORS FOR THIS QUERY:\n" + "".join(lines)
    if truncated:
        section += f"(List truncated to fit context. Total doctors on file: {len(doctors)})\n"

    return section, len(lines)


# =============================================================================
# KB CONTEXT TRIMMING
# =============================================================================

def build_kb_context(chunks: list) -> tuple[str, int]:
    """Trim each KB chunk and the total section to their character budgets."""
    if not chunks:
        return "", 0

    trimmed_chunks = []
    total_chars = 0

    for chunk in chunks:
        text = chunk.content.strip()
        if len(text) > KB_CHUNK_MAX_CHARS:
            text = text[:KB_CHUNK_MAX_CHARS].rsplit(" ", 1)[0] + "…"
        if total_chars + len(text) > KB_SECTION_MAX_CHARS:
            break
        trimmed_chunks.append(text)
        total_chars += len(text)

    if not trimmed_chunks:
        return "", 0

    return "\n---\n".join(trimmed_chunks), len(trimmed_chunks)


# =============================================================================
# AVAILABILITY — with typed error handling
# =============================================================================

def fetch_availability_context(
    question: str,
    sheet_id: str,
    hospital_id: int,
    today_str: str,
) -> str:
    """
    Fetch live doctor availability from Google Sheets and return a
    directive string for the system prompt.

    Three possible outcomes:

    1. SUCCESS — doctor matched and their status is known:
       Returns either an "ABSENT TODAY" warning or an "Available today"
       confirmation. The LLM uses this as authoritative ground truth.

    2. STALE CACHE FALLBACK — the live fetch failed but we have a recent
       cached result (from a successful fetch within the current process):
       Returns availability from cache, flagged as possibly stale so the
       LLM can qualify its answer appropriately.

    3. FULLY OFFLINE — fetch failed and no cache exists:
       Returns an explicit directive instructing the LLM NOT to guess
       and to redirect the patient to call reception. This is the safe
       default that prevents hallucinated availability information.

    The distinction between outcomes 2 and 3 matters clinically:
    stale-cache data from 4 minutes ago is usually still correct; a
    completely empty response with no data at all should never allow
    the model to invent an answer.
    """
    try:
        doctors_live_data = get_doctor_availability(sheet_id=sheet_id)

        # Successful fetch — resolve any doctor mentioned in the question
        doc_id, doc_name = resolve_doctor_id(question, doctors_live_data)

        if not doc_id:
            # No specific doctor mentioned — no availability context needed
            return ""

        doc_info = doctors_live_data.get(doc_id, {})
        absent_dates_raw = str(doc_info.get("absent_dates", ""))
        absent_dates = [d.strip() for d in absent_dates_raw.split(",") if d.strip()]

        if today_str in absent_dates:
            return (
                f"IMPORTANT LIVE STATUS: {doc_name} is ABSENT TODAY ({today_str}). "
                "Tell the patient they are unavailable and suggest they contact "
                "reception to reschedule or see another doctor."
            )
        else:
            return (
                f"LIVE STATUS: {doc_name} is available today ({today_str}) "
                "according to the live schedule."
            )

    except AvailabilityError as e:
        # Typed error from availability.py — log it properly so it surfaces
        # in Render's log stream, then attempt a graceful stale-cache fallback.
        logger.error(
            "[Availability] Fetch failed for hospital_id=%s sheet_id=%s: %s",
            hospital_id, sheet_id, str(e)
        )

        stale_data = get_cached_or_empty(sheet_id)

        if stale_data:
            # We have stale data — try to use it but flag it to the LLM
            doc_id, doc_name = resolve_doctor_id(question, stale_data)

            if doc_id:
                doc_info = stale_data.get(doc_id, {})
                absent_dates_raw = str(doc_info.get("absent_dates", ""))
                absent_dates = [d.strip() for d in absent_dates_raw.split(",") if d.strip()]

                if today_str in absent_dates:
                    return (
                        f"AVAILABILITY DATA (may be up to 5 minutes old): "
                        f"{doc_name} was marked ABSENT for today ({today_str}) "
                        "in the last known schedule. Advise the patient to confirm "
                        "by calling reception before visiting."
                    )
                else:
                    return (
                        f"AVAILABILITY DATA (may be up to 5 minutes old): "
                        f"{doc_name} was marked as available today ({today_str}) "
                        "in the last known schedule. Advise the patient to confirm "
                        "by calling reception if time-sensitive."
                    )

            # Stale data exists but doctor not found in it — still offline
            logger.info(
                "[Availability] Stale cache exists for sheet_id=%s but "
                "no doctor match found for question: %.80s",
                sheet_id, question
            )

        # No stale data at all, or no doctor match in stale data —
        # use the safe explicit directive so the LLM cannot guess.
        logger.warning(
            "[Availability] No usable data for hospital_id=%s. "
            "Using safe offline fallback.",
            hospital_id
        )
        return (
            "SYSTEM NOTE: Live doctor availability data is currently unreachable. "
            "You MUST NOT guess or fabricate whether any doctor is available. "
            "If the patient asks about a specific doctor's availability, tell them "
            "the live schedule is temporarily unavailable and ask them to call the "
            "hospital reception directly to confirm."
        )

    except Exception as e:
        # Unexpected error — log it and use the safe fallback
        logger.exception(
            "[Availability] Unexpected error for hospital_id=%s: %s",
            hospital_id, str(e)
        )
        return (
            "SYSTEM NOTE: Live doctor availability data is currently unreachable. "
            "You MUST NOT guess or fabricate whether any doctor is available. "
            "Ask the patient to call reception directly to confirm."
        )


# =============================================================================
# SHARED CONTEXT BUILDER
# =============================================================================

def build_context(request: ChatRequest, db: Session):
    """Assemble the system prompt and full OpenAI message list."""
    hospital_id = request.hospital_id
    question = request.question
    target_lang = request.language
    today_str = datetime.now().strftime("%d-%m-%Y")

    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    # 1. Doctor directory (relevance-filtered + budget-capped)
    all_doctors = db.query(Doctor).filter(Doctor.hospital_id == hospital_id).all()
    doctor_context, doctors_included = build_doctor_context(question, all_doctors)

    # 2. Live availability — now with typed error handling and safe fallback
    availability_context = ""
    if hospital.google_sheet_id:
        availability_context = fetch_availability_context(
            question=question,
            sheet_id=hospital.google_sheet_id,
            hospital_id=hospital_id,
            today_str=today_str,
        )

    # 3. Vector search (pgvector RAG) — budget-trimmed
    embed_resp = client.embeddings.create(input=question, model="text-embedding-3-small")
    raw_results = (
        db.query(KnowledgeBase)
        .filter(KnowledgeBase.hospital_id == hospital_id)
        .order_by(KnowledgeBase.embedding.cosine_distance(embed_resp.data[0].embedding))
        .limit(3)
        .all()
    )
    kb_context, chunks_included = build_kb_context(raw_results)

    # 4. Language + behaviour
    lang_instruction = (
        "IMPORTANT: Respond ONLY in Malayalam script (മലയാളം). Do not use English script."
        if target_lang == "ml"
        else "Respond strictly in English."
    )

    behavior_guidelines = """RESPONSE GUIDELINES:
- Malayalam: Use Manglish style — English technical terms in Malayalam script.
  e.g. 'കാർഡിയോളജി വിഭാഗം' not a literal translation.
- Tone: Professional but conversational, like a hospital receptionist.
- If information is not in your context, say so clearly — do not guess.
- Keep responses concise (1–2 sentences) unless listing multiple items."""

    # 5. Assemble system prompt
    system_prompt_parts = [
        f"You are Arogya, the AI Assistant for {hospital.name}.",
        f"Current Date: {today_str}",
        "",
        hospital.system_prompt or "",
        lang_instruction,
        "",
        behavior_guidelines,
        "",
        doctor_context,
    ]

    if availability_context:
        system_prompt_parts.append(availability_context)

    if kb_context:
        system_prompt_parts.extend(["", "ADDITIONAL KNOWLEDGE:", kb_context])

    system_prompt_parts.append(
        "\nRespond in the language used by the user. "
        "You have memory of this conversation — give coherent, non-repetitive answers."
    )

    system_prompt = "\n".join(system_prompt_parts)

    # 6. Budget telemetry
    prompt_chars = len(system_prompt)
    approx_tokens = prompt_chars // 4

    if prompt_chars > SYSTEM_PROMPT_WARN_CHARS:
        logger.warning(
            "System prompt exceeds soft limit for hospital_id=%s: "
            "%d chars (~%d tokens). doctors=%d/%d kb_chunks=%d",
            hospital_id, prompt_chars, approx_tokens,
            doctors_included, len(all_doctors), chunks_included,
        )
    else:
        logger.debug(
            "System prompt for hospital_id=%s: %d chars (~%d tokens) "
            "doctors=%d/%d kb_chunks=%d",
            hospital_id, prompt_chars, approx_tokens,
            doctors_included, len(all_doctors), chunks_included,
        )

    # 7. Full message list
    history_messages = build_history_messages(request.history or [])
    openai_messages = (
        [{"role": "system", "content": system_prompt}]
        + history_messages
        + [{"role": "user", "content": question}]
    )

    return system_prompt, openai_messages, hospital


# =============================================================================
# HISTORY HELPERS
# =============================================================================

def build_history_messages(history: List[HistoryMessage]) -> List[dict]:
    if not history:
        return []
    max_messages = MAX_HISTORY_TURNS * 2
    trimmed = history[-max_messages:]
    if trimmed and trimmed[0].role != "user":
        trimmed = trimmed[1:]
    return [{"role": msg.role, "content": msg.content} for msg in trimmed]


# =============================================================================
# PDF INGESTION HELPERS
# =============================================================================

def extract_text_from_pdf(pdf_bytes: bytes) -> tuple[str, int]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages_text = []
    for page_num, page in enumerate(doc):
        page_text = page.get_text("text").strip()
        if page_text:
            pages_text.append(f"[Page {page_num + 1}]\n{page_text}")
    page_count = len(doc)
    doc.close()
    return "\n\n".join(pages_text), page_count


def chunk_text(text: str) -> List[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=PDF_CHUNK_SIZE,
        chunk_overlap=PDF_CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    raw_chunks = splitter.split_text(text)
    return [c.strip() for c in raw_chunks if len(c.strip()) > 50]


def embed_chunks_batch(chunks: List[str]) -> List[List[float]]:
    embeddings = []
    batch_size = 100
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        resp = client.embeddings.create(input=batch, model="text-embedding-3-small")
        embeddings.extend([item.embedding for item in resp.data])
    return embeddings


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("/ingest")
async def ingest_knowledge(
    request: IngestRequest,
    db: Session = Depends(get_db)
):
    try:
        resp = client.embeddings.create(input=request.text, model="text-embedding-3-small")
        embedding = resp.data[0].embedding
        db.add(KnowledgeBase(
            hospital_id=request.hospital_id,
            content=request.text,
            embedding=embedding,
            created_at=datetime.utcnow()
        ))
        db.commit()
        return {"status": "success", "message": "Knowledge added to Arogya's brain"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload-pdf")
async def upload_pdf(
    file: UploadFile = File(...),
    hospital_id: int = Form(...),
    db: Session = Depends(get_db)
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="Only PDF files are accepted.")

    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=422, detail="Uploaded file is empty.")
    if not pdf_bytes.startswith(b"%PDF"):
        raise HTTPException(status_code=422, detail="File does not appear to be a valid PDF.")

    try:
        full_text, page_count = extract_text_from_pdf(pdf_bytes)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not read PDF: {e}")

    if not full_text.strip():
        raise HTTPException(
            status_code=422,
            detail="No readable text found. Scanned image-only PDFs are not supported."
        )

    chunks = chunk_text(full_text)
    if not chunks:
        raise HTTPException(status_code=422, detail="PDF text was too short to produce knowledge chunks.")

    try:
        embeddings = embed_chunks_batch(chunks)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding failed: {e}")

    try:
        for chunk_content, embedding in zip(chunks, embeddings):
            db.add(KnowledgeBase(
                hospital_id=hospital_id,
                content=chunk_content,
                embedding=embedding,
                created_at=datetime.utcnow()
            ))
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    return {
        "status": "success",
        "filename": file.filename,
        "pages_processed": page_count,
        "chunks_stored": len(chunks),
        "total_characters": sum(len(c) for c in chunks),
        "message": (
            f"'{file.filename}' processed successfully. "
            f"{page_count} pages → {len(chunks)} knowledge chunks stored for {hospital.name}."
        )
    }


@router.post("/chat")
async def chat_with_arogya(
    request: ChatRequest,
    db: Session = Depends(get_db)
):
    _, openai_messages, _ = build_context(request, db)

    ai_response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=openai_messages
    )

    usage = ai_response.usage
    db.add(UsageLedger(
        hospital_id=request.hospital_id,
        endpoint="/chat",
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens,
        estimated_cost=(usage.total_tokens / 1_000_000) * 0.15
    ))
    db.commit()

    return {"answer": ai_response.choices[0].message.content}


@router.post("/chat-stream")
async def chat_stream(
    request: ChatRequest,
    db: Session = Depends(get_db)
):
    _, openai_messages, _ = build_context(request, db)

    async def event_generator() -> AsyncGenerator[str, None]:
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0

        try:
            stream = await async_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=openai_messages,
                stream=True,
                stream_options={"include_usage": True}
            )

            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                token = delta.content if delta and delta.content else None
                if token:
                    yield f"data: {json.dumps(token)}\n\n"
                if chunk.usage:
                    prompt_tokens = chunk.usage.prompt_tokens
                    completion_tokens = chunk.usage.completion_tokens
                    total_tokens = chunk.usage.total_tokens

            yield "data: [DONE]\n\n"

            if total_tokens > 0:
                db.add(UsageLedger(
                    hospital_id=request.hospital_id,
                    endpoint="/chat-stream",
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    estimated_cost=(total_tokens / 1_000_000) * 0.15
                ))
                db.commit()

        except Exception as e:
            yield f"data: [ERROR] {str(e)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )