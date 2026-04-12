from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.base import Base
# Import the router objects from your endpoint files
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.hospitals import router as hospitals_router
from app.api.v1.endpoints.ai import router as ai_router
from app.db.session import engine
from app.api.v1.endpoints.appointments import router as appointments_router
from app.services.reminders import start_reminder_scheduler, stop_reminder_scheduler

app = FastAPI(title="Hospital AI Platform")
Base.metadata.create_all(bind=engine)
# --- CORS Configuration ---
# This allows both your local development and your live Vercel site to talk to this API
origins = [
    "https://hospital-ai-platform.vercel.app",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://hospital-ai-platform.vercel.app", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"], # Be explicit here
    allow_headers=["*"],
)
# --- Include Routers ---
# Note: The prefixes here combine with the @router paths in your endpoint files

# 1. Auth Router (Handles Login and Token Generation)
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])

# 2. Hospitals Router (Handles Staff management and Hospital settings)
app.include_router(hospitals_router, prefix="/api/v1/hospitals", tags=["hospitals"])

# 3. AI Router (Handles /chat, /ingest, and /upload-pdf)
# We use /api/v1/ai so that the frontend calls /api/v1/ai/chat
app.include_router(ai_router, prefix="/api/v1/ai", tags=["AI"])
app.include_router(appointments_router, prefix="/api/v1/appointments", tags=["Appointments"])
@app.on_event("startup")
def on_startup():
    start_reminder_scheduler()
    
@app.on_event("shutdown")
def on_shutdown():
    stop_reminder_scheduler()
@app.get("/")
def read_root():
    return {
        "status": "online",
        "message": "Welcome to the Hospital AI Platform API",
        "version": "v1.0.0"
    }