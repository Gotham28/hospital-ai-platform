# -*- coding: utf-8 -*-
"""
E2E test runner for Feature 4 (Relevance Gate) — Scenario 1 only re-run.
Scenario 2 already completed (appointment id=3, Charlie Nair).
Fixes:
  - sys.stdout.reconfigure(utf-8) to handle emoji in AI responses
  - Extra turns for Scenario 1 so the conversation reaches book_appointment
"""
import sys
import httpx
import json
import time

# Fix Windows cp1252 encoding issue for emoji in AI responses
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "http://localhost:8000/api/v1/ai/chat-stream"
HOSPITAL_ID = 15
TIMEOUT = 90.0


def chat(history: list, question: str, session_token: str) -> str:
    """Send one turn and return the full AI response text."""
    print(f"\n  USER: {question}")
    payload = {
        "question": question,
        "hospital_id": HOSPITAL_ID,
        "session_token": session_token,
        "history": history,
    }
    full_response = ""
    try:
        with httpx.stream("POST", BASE_URL, json=payload, timeout=TIMEOUT) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if line.startswith("data: ") and line != "data: [DONE]":
                    try:
                        chunk = json.loads(line[6:])
                        full_response += chunk
                    except json.JSONDecodeError:
                        full_response += line[6:]
    except Exception as e:
        print(f"  [HTTP ERROR] {e}")
        return ""

    history.append({"role": "user", "content": question})
    history.append({"role": "assistant", "content": full_response})
    preview = full_response[:400]
    print(f"  AI: {preview}{'...' if len(full_response) > 400 else ''}")
    return full_response


def run_scenario(name: str, turns: list) -> None:
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")
    sid = f"e2e_{int(time.time() * 1000)}"
    print(f"  session_token = {sid}")
    history = []
    for i, question in enumerate(turns):
        response = chat(history, question, sid)
        if not response:
            print(f"\n  [STALL] No response on turn {i+1}. Stopping.")
            break
        time.sleep(1)
    print(f"\n  [DONE] scenario finished. session_token={sid}")


# ── SCENARIO 1: Referral fast path — re-run with more turns ──────────────────
# Previous run stalled because the AI asked for a date after we gave all details
# at once. Now we feed details one piece at a time and confirm step-by-step.
run_scenario(
    "SCENARIO 1 (RE-RUN) — Referral Fast Path (hospital_id=15)",
    [
        # Turn 1: trigger booking intent
        "Hi, I'd like to book an appointment at this clinic.",
        # Turn 2: confirm referral
        "Yes, my doctor referred me here.",
        # Turn 3: choose doctor (only Dr. Smith available in this test DB)
        "I'd like to see Dr. Smith please.",
        # Turn 4: provide date
        "Tomorrow, July 23.",
        # Turn 5: morning
        "Morning, around 10am.",
        # Turn 6: name
        "Alice Johnson.",
        # Turn 7: age
        "I'm 32 years old.",
        # Turn 8: phone
        "My phone number is 9876543210.",
        # Turn 9: confirm
        "Yes, please confirm the booking.",
    ],
)
