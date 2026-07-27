from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime


class CustomerBase(BaseModel):
    name: str
    phone: Optional[str] = None
    notes: Optional[str] = None


class CustomerCreate(CustomerBase):
    pass


class CustomerAgg(BaseModel):
    total: float
    owed: float
    count: int


class CustomerOut(CustomerBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    agg: CustomerAgg

    class Config:
        from_attributes = True
