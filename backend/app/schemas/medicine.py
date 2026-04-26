from typing import Optional
from pydantic import BaseModel

class MedicineBase(BaseModel):
    name: str
    brand_name: Optional[str] = None
    category: Optional[str] = None
    price: Optional[float] = None
    stock_status: Optional[str] = "in_stock"
    requires_prescription: Optional[bool] = False

class MedicineCreate(MedicineBase):
    hospital_id: int

class MedicineUpdate(MedicineBase):
    name: Optional[str] = None

class Medicine(MedicineBase):
    id: int
    hospital_id: int

    class Config:
        from_attributes = True