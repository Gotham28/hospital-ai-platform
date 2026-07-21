"""
services/relevance.py
─────────────────────
Feature 4 — Rheumatology-relevance gate.

Provides a dedicated LLM call that is deliberately kept SEPARATE from the main
chat system prompt so the relevance check cannot be skipped, overridden, or
softened by the conversational model's tone/personality.

Public API
----------
check_relevance(criteria, answers, hospital_id) -> RelevanceVerdict
    Make the LLM relevance judgment call and return a structured verdict.

The caller (ai.py) owns all conversation-state management (patient_ctx keys,
turn sequencing, gating the booking flow). This module only does the LLM call.

patient_ctx keys managed by the caller (ai.py)
-----------------------------------------------
  relevance_stage    : str | None
      None                → gate not yet started for this booking attempt
      "asked_referral"    → Q1 ("has a doctor referred you?") sent to patient
      "asked_prior_docs"  → Q2 ("which specialists have you seen?") sent
      "asked_symptom"     → Q3 ("describe your main symptom") sent
      "done"              → verdict reached; gate complete for this attempt

  relevance_answers  : dict
      {"referral": str, "prior_docs": str, "symptom": str}
      Accumulated one key per stage as the patient answers.

  relevance_verdict  : dict | None
      {"is_relevant": bool|None, "needs_staff_review": bool, "reason": str}
      Written once, when stage transitions to "done".

Reset behaviour (managed by ai.py, not here)
--------------------------------------------
  When a booking successfully commits to the DB, ai.py stamps
  booking_completed_at in patient_ctx and increments booking_attempt.
  On the NEXT BOOKING intent within the same session, ai.py detects
  booking_completed_at and clears the three relevance_* keys so the gate
  re-runs from scratch for the new booking attempt.
"""

from __future__ import annotations

import logging
import json
from dataclasses import dataclass
from openai import AsyncOpenAI
import os

logger = logging.getLogger(__name__)

_api_key = os.getenv("OPENAI_API_KEY", "")
_async_client = AsyncOpenAI(api_key=_api_key)
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


@dataclass
class RelevanceVerdict:
    """
    Structured result of the relevance LLM call.

    is_relevant:        True  → patient appears relevant, proceed to booking
                        False → patient appears off-scope (still book as pending,
                                but set needs_staff_review=True)
                        None  → ambiguous; set needs_staff_review=True

    needs_staff_review: True when the AI is not confident OR when is_relevant
                        is False — staff must review before confirming the slot.

    reason:             Always populated. Stored as Appointment.relevance_reason
                        so staff can see the AI's reasoning in the admin table.
    """
    is_relevant: bool | None
    needs_staff_review: bool
    reason: str


async def check_relevance(
    relevance_criteria: str,
    patient_answers: dict,
    hospital_id: int,
) -> RelevanceVerdict:
    """
    Make a dedicated LLM call to assess whether this patient is relevant to
    the hospital's specialty, based on the clinic-configured criteria and the
    patient's collected answers.

    Parameters
    ----------
    relevance_criteria : str
        The hospital-configured criteria text (from hospital.relevance_criteria).
        This is set by the clinic admin; this function never invents wording.

    patient_answers : dict
        Keys: "referral" (str|None), "prior_docs" (str|None), "symptom" (str|None)
        Populated as the multi-turn gate progresses. Pass whatever is collected so
        far — the prompt handles partial information gracefully.

    hospital_id : int
        Used only for logging — ensures log lines are tenant-attributable.
        Never used in the LLM prompt to avoid leaking tenant identity to the model.

    Returns
    -------
    RelevanceVerdict
        On any LLM failure, returns a safe conservative verdict:
        needs_staff_review=True so a human always reviews edge cases.
    """
    referral   = patient_answers.get("referral") or "Not provided"
    prior_docs = patient_answers.get("prior_docs") or "Not provided"
    symptom    = patient_answers.get("symptom") or "Not provided"

    system_prompt = (
        "You are a clinical triage assistant for a specialty medical clinic. "
        "Your job is to assess whether a patient's situation matches the clinic's "
        "specialty criteria, based on the information they provided. "
        "You must be conservative: if in any doubt, set needs_staff_review to true "
        "so a human reviews. Never auto-decline a patient — that decision belongs to staff."
    )

    user_prompt = f"""CLINIC SPECIALTY CRITERIA:
{relevance_criteria}

PATIENT-PROVIDED INFORMATION:
- Was the patient referred by a doctor? {referral}
- Previous specialists/doctors consulted for this condition: {prior_docs}
- Main symptom described: {symptom}

Based on the criteria and the patient's answers, assess relevance.

Return a JSON object with exactly these fields:
{{
  "is_relevant": true | false | null,
  "needs_staff_review": true | false,
  "reason": "one or two sentence explanation of the verdict"
}}

Rules:
- Set is_relevant=true if the patient clearly matches the criteria.
- Set is_relevant=false if the patient clearly does NOT match.
- Set is_relevant=null if you genuinely cannot tell from the information given.
- Set needs_staff_review=true whenever is_relevant is false or null,
  OR when is_relevant is true but there is notable ambiguity.
- The reason field must always be populated — staff will read it.
- Return ONLY the JSON object. No markdown, no explanation."""

    try:
        resp = await _async_client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.0,
            max_tokens=200,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
        )
        raw = json.loads(resp.choices[0].message.content)
        is_relevant = raw.get("is_relevant")        # True, False, or None
        needs_review = bool(raw.get("needs_staff_review", True))
        reason = str(raw.get("reason", "")).strip() or "No reason provided by AI."

        # Enforce: if is_relevant is not True, always flag for staff review.
        if is_relevant is not True:
            needs_review = True

        if needs_review:
            logger.info(
                "[Relevance] hospital_id=%s is_relevant=%s needs_staff_review=%s reason=%r",
                hospital_id, is_relevant, needs_review, reason[:120],
            )
        else:
            logger.info(
                "[Relevance] hospital_id=%s is_relevant=%s needs_staff_review=%s",
                hospital_id, is_relevant, needs_review,
            )
        return RelevanceVerdict(
            is_relevant=is_relevant,
            needs_staff_review=needs_review,
            reason=reason,
        )

    except Exception as exc:
        logger.warning(
            "[Relevance] LLM call failed for hospital_id=%s: %s — defaulting to staff review",
            hospital_id, exc,
        )
        return RelevanceVerdict(
            is_relevant=None,
            needs_staff_review=True,
            reason="Relevance check could not be completed automatically. Please review manually.",
        )


async def check_referral_intent(patient_answer: str, hospital_id: int) -> bool:
    """
    Evaluates whether the patient's answer to "Have you been referred?" means yes.
    Returns True if the patient clearly indicates they were referred.
    Returns False if they were not referred, or if it's ambiguous/unclear.
    """
    system_prompt = (
        "You are a classification assistant. The user was asked if they were referred "
        "to a clinic by a doctor. Read their answer and determine if they are saying YES "
        "they were referred. If they say no, or give an unrelated/ambiguous answer, return false."
    )
    user_prompt = f"Patient's answer: {patient_answer}\n\nReturn a JSON object: {{\"referred\": true|false}}"

    try:
        resp = await _async_client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.0,
            max_tokens=20,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
        )
        raw = json.loads(resp.choices[0].message.content)
        is_referred = bool(raw.get("referred", False))
        logger.info("[Relevance] hospital_id=%s referral check answer=%r parsed_as=%s", 
                    hospital_id, patient_answer[:100], is_referred)
        return is_referred
    except Exception as exc:
        logger.warning("[Relevance] Referral LLM check failed for hospital_id=%s: %s", hospital_id, exc)
        return False

