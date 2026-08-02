"""
app/services/booking.py

Booking-related helpers extracted from app/api/v1/endpoints/ai.py —
Stage 5 of the service extraction refactor.

Contains:
  - _RELEVANCE_STAGES      : ordered stage list for the multi-turn relevance Q&A
  - _reset_relevance_gate  : clear gate keys when a new booking attempt starts
  - _is_new_booking_attempt: detect second booking in the same session
  - normalise_booking_input: LLM-backed field normaliser (phone, name, age, date…)
  - classify_user_intent   : LLM-backed intent classifier (BOOKING/STATUS/CANCEL/OTHER)

All call sites in ai.py are unchanged; only the import source moved.
No schema changes, no new models, no API surface changes.
"""

import os
import json
import logging
from datetime import datetime

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# OpenAI client — re-created here identically to the pattern in rag.py /
# translation.py so this module is self-contained.
# ---------------------------------------------------------------------------
_api_key = os.getenv("OPENAI_API_KEY")
if not _api_key:
    raise RuntimeError("OPENAI_API_KEY environment variable is not set.")

async_client = AsyncOpenAI(api_key=_api_key)
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


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
