from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Create the database engine with anti-disconnect safety measures
engine = create_engine(
    settings.SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,      # Tests the connection before using it (Fixes EOF errors)
    pool_recycle=1800,       # Proactively recycles connections every 30 minutes
)

# Create a Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)