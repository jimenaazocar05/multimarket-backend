from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime


class SupplierBase(BaseModel):
    name: str
    phone: Optional[str] = None
    notes: Optional[str] = None


class SupplierCreate(SupplierBase):
    pass


class SupplierAgg(BaseModel):
    total: float
    owed: float
    count: int


class SupplierOut(SupplierBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    agg: SupplierAgg

    class Config:
        from_attributes = True
