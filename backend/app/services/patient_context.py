"""
services/patient_context.py
────────────────────────────
Patient personalisation — Redis-backed session context that persists
language preference, doctor/department interest, seen topics, and booking
metadata across turns within a single session (TTL: 10 minutes).

Extracted from app.api.v1.endpoints.ai — Stage 3 of service extraction.

Public API
----------
_patient_ctx_key(hospital_id, session_token)  -> str
_load_patient_ctx(hospital_id, session_token) -> dict
_save_patient_ctx(hospital_id, session_token, ctx) -> None
_update_patient_ctx(hospital_id, session_token, *, language, question_en,
                    history, db) -> dict
_build_patient_ctx_block(ctx) -> str
_log_task_completion(hospital_id, session_token, ctx, outcome) -> None

Redis key schema
----------------
  patient_ctx:{hospital_id}:{session_token}
  TTL: PATIENT_CTX_TTL seconds (600 — matches BOOKING_SESSION_TTL)

Context dict schema
-------------------
{
  "session_started_at": float,       # time.time() at session start
  "turn_count":         int,
  "language":           "en" | "ml",
  "doctor_id":          int | None,
  "doctor_name":        str | None,
  "department":         str | None,  # canonical dept string
  "seen_topics":        list[str],   # e.g. ["pharmacy", "appointment"]
  "_is_new_session":    bool,
  # booking state (set by ai.py booking flow):
  "booking_completed_at": float | None,
  "booking_attempt":      int | None,
  # relevance gate (set by ai.py relevance flow):
  "relevance_stage":   str | None,
  "relevance_answers": dict | None,
  "relevance_verdict": dict | None,
}
"""
import json
import logging
import os
import re
import time

import redis

from app.services.vocabulary import _DEPT_SYNONYMS

logger = logging.getLogger(__name__)

# =============================================================================
# REDIS CLIENT
# =============================================================================
# Constructed once at import time, same pattern as ai.py.
_redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
_redis = redis.from_url(_redis_url, decode_responses=True)

# =============================================================================
# CONSTANTS
# =============================================================================
PATIENT_CTX_TTL = 600   # matches BOOKING_SESSION_TTL; both keys expire together


# =============================================================================
# REDIS KEY
# =============================================================================

def _patient_ctx_key(hospital_id: int, session_token: str) -> str:
    """Redis key for patient personalisation (separate from booking state)."""
    return f"patient_ctx:{hospital_id}:{session_token}"


# =============================================================================
# LOAD / SAVE
# =============================================================================

def _load_patient_ctx(hospital_id: int, session_token: str) -> dict:
    """
    Return the current patient context dict, or {} if none exists yet.
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
        logger.info("[PatientCtx] saved: %s", json.dumps(ctx))
    except Exception as exc:
        logger.warning("[PatientCtx] save failed: %s", exc)


# =============================================================================
# UPDATE (called once per request, before streaming)
# =============================================================================

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
    # Import here to avoid a circular import: Doctor is an ORM model that
    # transitively imports from app.db which may not be ready at module load.
    from app.models.doctor import Doctor  # noqa: PLC0415

    ctx = _load_patient_ctx(hospital_id, session_token)
    is_new_session = not ctx

    # ── 0. Session timing / turn count (for task-completion metric) ───────
    if "session_started_at" not in ctx:
        ctx["session_started_at"] = time.time()
    ctx["turn_count"] = ctx.get("turn_count", 0) + 1

    # ── 1. Language preference ────────────────────────────────────────────
    ctx["language"] = language   # always authoritative from the live request

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
    # Uses _DEPT_SYNONYMS from vocabulary.py — no extra work needed.
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


# =============================================================================
# SYSTEM-PROMPT BLOCK RENDERER
# =============================================================================

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


# =============================================================================
# TASK-COMPLETION LOGGING
# =============================================================================

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
