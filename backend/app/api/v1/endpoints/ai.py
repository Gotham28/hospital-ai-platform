import os
import re
import fitz  # PyMuPDF
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
from openai import OpenAI
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, Body, UploadFile, File

from app.api.deps import get_db, get_current_tenant
from app.models.hospital import Hospital 
from app.models.knowledge import KnowledgeBase 
from app.models.usage import UsageLedger
from app.models.doctor import Doctor 
from app.availability import get_doctor_availability

from langchain_text_splitters import RecursiveCharacterTextSplitter

router = APIRouter()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# -------------------------------------------------
# MODELS
# -------------------------------------------------

class ChatRequest(BaseModel):
    question: str
    hospital_id: int 
    language: Optional[str] = "en"  # NEW: Supports 'en' or 'ml' for regional responses

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
        norm_name = normalize_name(d.get("name", ""))
        query_tokens, name_tokens = set(normalized_query.split()), set(norm_name.split())
        
        if not query_tokens or not name_tokens: continue
        
        score = len(query_tokens & name_tokens) / len(name_tokens)
        if score > best_score:
            best_score = score
            best_match = (doctor_id, d.get("name"))

    return best_match if best_score >= 0.5 else (None, None)

# -------------------------------------------------
# ENDPOINTS
# -------------------------------------------------

@router.post("/ingest")
async def ingest_hospital_knowledge(
    content: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    hospital_id: int = Depends(get_current_tenant)
):
    try:
        splitter = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=200)
        chunks = splitter.split_text(content)

        for chunk in chunks:
            response = client.embeddings.create(input=chunk, model="text-embedding-3-small")
            vector = response.data[0].embedding

            new_entry = KnowledgeBase(
                hospital_id=hospital_id,
                content=chunk,
                embedding=vector
            )
            db.add(new_entry)
        
        db.commit()
        return {"status": "success", "message": f"Arogya processed {len(chunks)} knowledge chunks."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload-pdf")
async def upload_pdf(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    hospital_id: int = Depends(get_current_tenant)
):
    try:
        pdf_bytes = await file.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        full_text = "\n".join([page.get_text() for page in doc])
        return await ingest_hospital_knowledge(content=full_text, db=db, hospital_id=hospital_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF Processing failed: {str(e)}")

@router.post("/chat")
async def chat_with_arogya(
    request: ChatRequest, 
    db: Session = Depends(get_db)
):
    hospital_id = request.hospital_id
    question = request.question
    target_lang = request.language

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
                availability_context = f"LIVE STATUS for {doc_name}: {doctors_live_data.get(doc_id)} "
        except Exception:
            availability_context = "Live doctor availability currently offline."

    # 3. VECTOR SEARCH (KNOWLEDGE BASE PDFs)
    resp = client.embeddings.create(input=question, model="text-embedding-3-small")
    results = db.query(KnowledgeBase).filter(KnowledgeBase.hospital_id == hospital_id).order_by(
        KnowledgeBase.embedding.cosine_distance(resp.data[0].embedding)
    ).limit(3).all()
    kb_context = "\n".join([r.content for r in results])

    # 4. FINAL COMPLETION WITH REGIONAL LOGIC
    # NEW: Instructing GPT-4o-mini to respond in the selected language
    lang_instruction = "IMPORTANT: Respond strictly in Malayalam (മലയാളം)." if target_lang == "ml" else "Respond in English."

    system_prompt = f"""
    You are Arogya, the AI for {hospital.name}.
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
    
    # 5. Save to Ledger
    usage = ai_response.usage
    db.add(UsageLedger(
        hospital_id=hospital_id,
        endpoint="/chat",
        total_tokens=usage.total_tokens,
        estimated_cost=(usage.total_tokens / 1_000_000) * 0.15
    ))
    db.commit()

    return {"answer": ai_response.choices[0].message.content}