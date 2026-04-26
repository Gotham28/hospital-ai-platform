"""
Run once to backfill embeddings for all existing doctors.
Usage: python embed_doctors.py
"""
import os
from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI
from app.db.session import SessionLocal
from app.models.doctor import Doctor

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
db = SessionLocal()

def make_embed_text(doctor: Doctor) -> str:
    parts = [f"Dr. {doctor.name}"]
    if doctor.department:
        parts.append(f"{doctor.department} specialist")
    if doctor.base_schedule:
        parts.append(f"schedule: {doctor.base_schedule}")
    return ", ".join(parts)

try:
    doctors = db.query(Doctor).filter(Doctor.embedding == None).all()
    print(f"Found {len(doctors)} doctors without embeddings.")

    for i, doctor in enumerate(doctors):
        text = make_embed_text(doctor)
        resp = client.embeddings.create(input=text, model="text-embedding-3-small")
        doctor.embedding = resp.data[0].embedding
        print(f"  [{i+1}/{len(doctors)}] Embedded: {doctor.name} ({doctor.department})")

    db.commit()
    print("Done. All doctors embedded.")
except Exception as e:
    db.rollback()
    print(f"Error: {e}")
finally:
    db.close()