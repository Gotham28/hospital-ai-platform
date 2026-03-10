from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
# These imports are likely bringing in the Router objects directly
from app.api.v1.endpoints import hospitals, auth, ai 

app = FastAPI(title="Hospital AI Platform")

# --- CORS Configuration ---
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Include Routers ---
# Since 'auth', 'hospitals', and 'ai' are likely already the Router objects,
# we remove the '.router' suffix to fix the AttributeError.

# 1. Auth Router (Login/Token)
app.include_router(auth, prefix="/api/v1/auth", tags=["auth"])

# 2. Hospitals Router (Staff/Settings)
app.include_router(hospitals, prefix="/api/v1/hospitals", tags=["hospitals"])

# 3. AI Router (Chat/Training)
app.include_router(ai, prefix="/api/v1/ai", tags=["AI"])

@app.get("/")
def read_root():
    return {"message": "Welcome to Hospital AI Platform API"}