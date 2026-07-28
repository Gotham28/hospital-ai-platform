# -*- coding: utf-8 -*-
import sys
import httpx
import json
import time
from app.db.session import SessionLocal
import app.db.base
from app.models.appointment import Appointment

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "http://localhost:8000/api/v1/ai/chat-stream"
HOSPITAL_ID = 15
TIMEOUT = 90.0

def chat(history: list, question: str, session_token: str) -> str:
    print(f"\n  USER: {question}")
    payload = {
        "question": question,
        "hospital_id": HOSPITAL_ID,
        "session_token": session_token, "language": "ml",
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
    sid = f"malayalam_{int(time.time() * 1000)}"
    print(f"  session_token = {sid}")
    history = []
    for i, question in enumerate(turns):
        response = chat(history, question, sid)
        if not response:
            print(f"\n  [STALL] No response on turn {i+1}. Stopping.")
            break
        time.sleep(1)
    print(f"\n  [DONE] scenario finished. session_token={sid}")

run_scenario(
    "SCENARIO MALAYALAM — Referral Fast Path (hospital_id=15)",
    [
        "എനിക്ക് ഈ ക്ലിനിക്കിൽ ഒരു അപ്പോയിന്റ്മെന്റ് ബുക്ക് ചെയ്യണം", # Booking intent
        "അതെ, ഒരു ഡോക്ടർ എന്നെ റഫർ ചെയ്തു", # Confirmed referral
        "എനിക്ക് ഡോക്ടർ സ്മിത്തിനെ കാണണം", # Doctor
        "നാളെ, ജൂലൈ 23", # Date
        "രാവിലെ 10 മണിക്ക്", # Time
        "ആലീസ് ജോൺസൺ", # Name
        "എനിക്ക് 32 വയസ്സാണ്", # Age
        "എന്റെ ഫോൺ നമ്പർ 9876543210 ആണ്", # Phone
        "അതെ, ദയവായി ബുക്കിംഗ് സ്ഥിരീകരിക്കുക", # Confirm
    ],
)

def check_and_cleanup_appointment(phone: str):
    print("\n  [DB] Checking for created appointment...")
    db = SessionLocal()
    try:
        apt = db.query(Appointment).filter(Appointment.patient_phone == phone).order_by(Appointment.id.desc()).first()
        if apt:
            print(f"  [DB] Success! Found appointment ID: {apt.id}, Ref: {apt.reference_number}")
            print(f"  [DB] Details - Name: {apt.patient_name}, Doctor ID: {apt.doctor_id}")
            print(f"  [DB] Needs Staff Review: {apt.needs_staff_review}")
            
            # Scoped cleanup
            db.delete(apt)
            db.commit()
            print("  [DB] Cleanup complete. Test appointment deleted.")
        else:
            print("  [DB] FAILED: Could not find appointment for phone:", phone)
    finally:
        db.close()

check_and_cleanup_appointment("9876543210")

