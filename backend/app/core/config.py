from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
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
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_WHATSAPP_NUMBER: str = ""

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