from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import the router objects from your endpoint files
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.hospitals import router as hospitals_router
from app.api.v1.endpoints.ai import router as ai_router

app = FastAPI(title="Hospital AI Platform")

# --- CORS Configuration ---
# This allows both your local development and your live Vercel site to talk to this API
origins = [
    "https://hospital-ai-platform.vercel.app",
    "http://localhost:3000",
    "http://localhost:5173",  # Vite's default port
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Allows GET, POST, OPTIONS, etc.
    allow_headers=["*"],  # Allows Authorization headers
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

@app.get("/")
def read_root():
    return {
        "status": "online",
        "message": "Welcome to the Hospital AI Platform API",
        "version": "v1.0.0"
    }