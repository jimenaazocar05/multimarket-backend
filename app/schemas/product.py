from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime


class ProductBase(BaseModel):
    code: Optional[str] = None
    name: str
    cost: float = 0
    price: float = 0
    low_stock_threshold: float = 5
    unit: str = "unidad"
    active: bool = True
    notes: Optional[str] = None


class ProductCreate(ProductBase):
    stock: float = 0  # solo se permite fijar stock en la creación


class ProductUpdate(ProductBase):
    pass  # sin stock — el stock solo cambia vía /api/inventory/adjust (Etapa 4)


class ProductOut(ProductBase):
    id: UUID
    stock: float
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
