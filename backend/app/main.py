from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.base import Base
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.hospitals import router as hospitals_router
from app.api.v1.endpoints.ai import router as ai_router
from app.db.session import engine
from app.api.v1.endpoints.appointments import router as appointments_router
from app.services.reminders import start_reminder_scheduler, stop_reminder_scheduler
from app.api.v1.endpoints.medicines import router as medicines_router
from app.api.v1.endpoints.lab_tests import router as lab_tests_router
from app.api.v1.endpoints.doctor_availability import router as availability_router
import os

app = FastAPI(title="Hospital AI Platform")
Base.metadata.create_all(bind=engine)

# Single source of truth for allowed origins
ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv(
        "ALLOWED_ORIGINS",
        "https://hospital-ai-platform.vercel.app,http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"
    ).split(",") if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router,         prefix="/api/v1/auth",         tags=["auth"])
app.include_router(hospitals_router,    prefix="/api/v1/hospitals",    tags=["hospitals"])
app.include_router(ai_router,           prefix="/api/v1/ai",           tags=["AI"])
app.include_router(appointments_router, prefix="/api/v1/appointments", tags=["Appointments"])
app.include_router(medicines_router, prefix="/api/v1/medicines", tags=["Medicines"])
app.include_router(lab_tests_router, prefix="/api/v1/lab-tests", tags=["Lab Tests"])
app.include_router(availability_router, prefix="/api/v1/availability", tags=["Doctor Availability"])

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