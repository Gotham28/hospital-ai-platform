from sqlalchemy.orm import Session
from passlib.context import CryptContext
from app.models.user import User
from app.schemas.user import UserCreate

# FIX #2: Use a real password hashing context, same as auth.py.
# The old code used `user.password + "notreallyhashed"` — plaintext storage.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_user(db: Session, user_id: int):
    return db.query(User).filter(User.id == user_id).first()

def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()

def create_user(db: Session, user: UserCreate):
    # FIX #2: Hash the password properly with bcrypt.
    hashed_password = pwd_context.hash(user.password)

    db_obj = User(
        email=user.email,
        hashed_password=hashed_password,
        full_name=user.full_name,
        hospital_id=user.hospital_id,
        is_superuser=user.is_superuser,
        is_active=user.is_active,
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj