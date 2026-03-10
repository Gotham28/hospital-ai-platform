from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Core
    PROJECT_NAME: str = "Hospital AI Platform"
    API_V1_STR: str = "/api/v1"
    
    # Database (Matches your .env fields)
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

    # Helper to build the URL dynamically
    @property
    def SQLALCHEMY_DATABASE_URL(self) -> str:
        if self.SQLALCHEMY_DATABASE_URI:
            return self.SQLALCHEMY_DATABASE_URI
        
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    class Config:
        case_sensitive = False
        env_file = ".env"
        extra = "ignore"  # CRITICAL: This stops the crash if .env has extra fields

settings = Settings()