from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.user import UserCreate

def get_user(db: Session, user_id: int):
    return db.query(User).filter(User.id == user_id).first()

def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()

def create_user(db: Session, user: UserCreate):
    # TODO: Hash the password later!
    fake_hashed_password = user.password + "notreallyhashed"
    
    db_obj = User(
        email=user.email,
        hashed_password=fake_hashed_password,
        full_name=user.full_name,
        hospital_id=user.hospital_id,
        is_superuser=user.is_superuser,
        is_active=user.is_active,
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj