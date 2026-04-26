import os
from typing import Generator
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from app.db.session import SessionLocal

# FIX #1: Load SECRET_KEY from environment, never hardcode it.
# Set JWT_SECRET in your .env and Render environment variables.
SECRET_KEY = os.getenv("JWT_SECRET", "dev-secret-key-change-in-production")
ALGORITHM = "HS256"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

def get_db() -> Generator:
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()

def get_current_tenant(token: str = Depends(oauth2_scheme)) -> int:
    """
    The Magic Key: Extracts the hospital_id from the JWT.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        hospital_id = payload.get("hospital_id")
        role = payload.get("role")
        
        # FIX: Allow superadmins to bypass the null tenant check
        if hospital_id is None and role != "superadmin":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials: No tenant ID found",
            )
        return hospital_id
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
def get_current_user_role(token: str = Depends(oauth2_scheme)) -> str:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("role", "staff")
    except JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

def require_superadmin(role: str = Depends(get_current_user_role)):
    if role != "superadmin":
        raise HTTPException(status_code=403, detail="Access denied")
    
def get_token_payload(token: str = Depends(oauth2_scheme)) -> dict:
    """
    Decodes the JWT and returns the payload (role, hospital_id, sub) 
    so routes can verify permissions.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )