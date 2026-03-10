from typing import Optional
from pydantic import BaseModel, EmailStr

# Shared properties
class UserBase(BaseModel):
    email: EmailStr
    is_active: Optional[bool] = True
    is_superuser: bool = False
    full_name: Optional[str] = None
    hospital_id: Optional[int] = None

# Properties to receive on creation
class UserCreate(UserBase):
    password: str

# Properties to receive on update
class UserUpdate(UserBase):
    password: Optional[str] = None

# Properties to return to client
class User(UserBase):
    id: int
    
    class Config:
        from_attributes = True