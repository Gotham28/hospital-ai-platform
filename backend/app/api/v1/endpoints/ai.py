import os
import re
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
from openai import OpenAI
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_db
from app.models.hospital import Hospital 
from app.models.knowledge import KnowledgeBase 
from app.models.usage import UsageLedger
from app.models.doctor import Doctor 
from app.availability import get_doctor_availability

router = APIRouter()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# -------------------------------------------------
# MODELS
# -------------------------------------------------
class IngestRequest(BaseModel):
    hospital_id: int
    text: str
class ChatRequest(BaseModel):
    question: str
    hospital_id: int 
    language: Optional[str] = "en"

# -------------------------------------------------
# UTILITIES
# -------------------------------------------------

def normalize_name(text: str) -> str:
    text = text.lower()
    text = re.sub(r"dr\.?", "", text)
    text = re.sub(r"[^a-z\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()

def resolve_doctor_id(user_text: str, doctor_data: dict):
    normalized_query = normalize_name(user_text)
    best_match, best_score = None, 0

    for doctor_id, d in doctor_data.items():
        name = d.get("name", "") if isinstance(d, dict) else str(d)
        norm_name = normalize_name(name)
        query_tokens, name_tokens = set(normalized_query.split()), set(norm_name.split())
        
        if not query_tokens or not name_tokens: continue
        
        score = len(query_tokens & name_tokens) / len(name_tokens)
        if score > best_score:
            best_score = score
            best_match = (doctor_id, name)

    return best_match if best_score >= 0.5 else (None, None)

# -------------------------------------------------
# ENDPOINT
# -------------------------------------------------
@router.post("/ingest")
async def ingest_knowledge(
    request: IngestRequest, 
    db: Session = Depends(get_db)
):
    try:
        # Create the embedding (this is what allows the vector search to work)
        resp = client.embeddings.create(
            input=request.text, 
            model="text-embedding-3-small"
        )
        embedding = resp.data[0].embedding

        # Save to the KnowledgeBase table
        new_entry = KnowledgeBase(
            hospital_id=request.hospital_id,
            content=request.text,
            embedding=embedding,
            created_at=datetime.utcnow()
        )
        db.add(new_entry)
        db.commit()
        
        return {"status": "success", "message": "Knowledge added to Arogya's brain"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
@router.post("/chat")
async def chat_with_arogya(
    request: ChatRequest, 
    db: Session = Depends(get_db)
):
    hospital_id = request.hospital_id
    question = request.question
    target_lang = request.language
    today_str = datetime.now().strftime("%d-%m-%Y") 

    hospital = db.query(Hospital).filter(Hospital.id == hospital_id).first()
    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")
    
    # 1. SEARCH DOCTOR DATABASE (Static Directory)
    doctors_list = db.query(Doctor).filter(Doctor.hospital_id == hospital_id).all()
    doctor_directory_context = "LIST OF DOCTORS AND SPECIALTIES:\n"
    for d in doctors_list:
        doctor_directory_context += f"- {d.name} ({d.department}): Schedule {d.base_schedule}\n"

    # 2. FETCH LIVE AVAILABILITY (GOOGLE SHEETS)
    availability_context = ""
    if hospital.google_sheet_id:
        try:
            doctors_live_data = get_doctor_availability(sheet_id=hospital.google_sheet_id)
            doc_id, doc_name = resolve_doctor_id(question, doctors_live_data)
            
            if doc_id:
                doc_info = doctors_live_data.get(doc_id)
                absent_dates = str(doc_info.get("absent_dates", ""))
                
                if today_str in [date.strip() for date in absent_dates.split(",")]:
                    availability_context = f"IMPORTANT LIVE STATUS: {doc_name} is ABSENT TODAY ({today_str}). Tell the user they are unavailable."
                else:
                    availability_context = f"LIVE STATUS for {doc_name}: Available today ({today_str})."
        except Exception as e:
            availability_context = f"Availability sync temporarily offline."

    # 3. VECTOR SEARCH (KNOWLEDGE BASE PDFs)
    resp = client.embeddings.create(input=question, model="text-embedding-3-small")
    results = db.query(KnowledgeBase).filter(KnowledgeBase.hospital_id == hospital_id).order_by(
        KnowledgeBase.embedding.cosine_distance(resp.data[0].embedding)
    ).limit(3).all()
    kb_context = "\n".join([r.content for r in results])

    # 4. FINAL COMPLETION & LANGUAGE
    if target_lang == "ml":
        lang_instruction = "IMPORTANT: Respond ONLY in Malayalam script (മലയാളം). Do not use English script."
    else:
        lang_instruction = "Respond strictly in English."

    system_prompt = f"""
    You are Arogya, the AI Assistant for {hospital.name}. 
    Current Date: {today_str}
    
    {hospital.system_prompt}
    {lang_instruction}

    {doctor_directory_context}
    {availability_context}
    
    ADDITIONAL KNOWLEDGE:
    {kb_context}
    """
    
    ai_response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt}, 
            {"role": "user", "content": question}
        ]
    )
    
    # 5. SAVE TO USAGE LEDGER
    usage = ai_response.usage
    db.add(UsageLedger(
        hospital_id=hospital_id,
        endpoint="/chat",
        total_tokens=usage.total_tokens,
        estimated_cost=(usage.total_tokens / 1_000_000) * 0.15
    ))
    db.commit()

    return {"answer": ai_response.choices[0].message.content}