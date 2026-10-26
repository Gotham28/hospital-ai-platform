from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from dotenv import load_dotenv

# Compute absolute path to backend/.env relative to this file
_env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(_env_path)

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_env_path), extra="ignore")
    # Core
    PROJECT_NAME: str = "Hospital AI Platform"
    API_V1_STR: str = "/api/v1"
    
    # 1. ADD THIS LINE: This maps the Render environment variable to your code
    DATABASE_URL: Optional[str] = None 

    # Database Defaults (Keep these for local dev)
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "NewStrongPassword123!"
    POSTGRES_DB: str = "hospital_ai"
    POSTGRES_PORT: str = "5432"
    
    # Optional: If you want to override the full URL
    SQLALCHEMY_DATABASE_URI: Optional[str] = None

    # App Secrets
    REDIS_URL: str = "redis://localhost:6379"
    OPENAI_API_KEY: str = "sk-placeholder"
    JWT_SECRET: str = "supersecret"
    SARVAM_API_KEY: str = ""
    # Meta welcome messages stay disabled until sender, templates and portals are approved.
    META_WHATSAPP_ENABLED: bool = False
    META_WHATSAPP_ACCESS_TOKEN: str = ""
    META_WHATSAPP_PHONE_NUMBER_ID: str = ""
    META_WHATSAPP_GRAPH_VERSION: str = ""
    META_WHATSAPP_APP_SECRET: str = ""
    META_WHATSAPP_VERIFY_TOKEN: str = ""
    META_WHATSAPP_TEMPLATE_EN: str = ""
    META_WHATSAPP_TEMPLATE_ML: str = ""
    # TODO: supply the exact approved copy, never a generated welcome/disclaimer.
    META_WHATSAPP_TEMPLATE_BODY_EN: str = ""
    META_WHATSAPP_TEMPLATE_BODY_ML: str = ""
    META_WHATSAPP_LANGUAGE_EN: str = "en_US"
    META_WHATSAPP_LANGUAGE_ML: str = "ml"
    PUBLIC_PATIENT_BASE_URL: str = ""
    META_WHATSAPP_ENABLED_HOSPITAL_SLUGS: str = ""
    WHATSAPP_RECIPIENT_HASH_SECRET: str = ""

    # CORS allowed origins — read from backend/.env for local dev, or from the
    # hosting platform's environment variables for production. The default is
    # dev-origins-only; production must supply its own explicit value via env var.
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"

    # Helper to build the URL dynamically
    @property
    def SQLALCHEMY_DATABASE_URL(self) -> str:
        # Check Render's DATABASE_URL first
        if self.DATABASE_URL:
            # Render often gives 'postgres://', but SQLAlchemy needs 'postgresql://'
            return self.DATABASE_URL.replace("postgres://", "postgresql://", 1)
        
        # Fallback to local construction
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

settings = Settings()
