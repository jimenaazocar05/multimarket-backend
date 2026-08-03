from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal
from uuid import UUID
from datetime import datetime, date


class SaleItemIn(BaseModel):
    product_id: UUID
    product_name: str
    quantity: float = Field(gt=0)
    unit_price: float = Field(ge=0)
    unit_cost: float = Field(ge=0)


class SaleCreate(BaseModel):
    customer_id: Optional[UUID] = None
    customer_name: Optional[str] = None
    status: Literal["paid", "credit"]
    notes: Optional[str] = None
    items: list[SaleItemIn]

    @field_validator("items")
    @classmethod
    def at_least_one_item(cls, v):
        if not v:
            raise ValueError("La venta debe tener al menos un producto")
        return v


class SaleItemOut(BaseModel):
    id: UUID
    product_id: Optional[UUID]
    product_name: str
    quantity: float
    unit_price: float
    unit_cost: float
    subtotal: float

    class Config:
        from_attributes = True


class PaymentOut(BaseModel):
    id: UUID
    amount: float
    payment_date: date
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class SaleOut(BaseModel):
    id: UUID
    sale_date: datetime
    customer_id: Optional[UUID]
    customer_name: Optional[str]
    total: float
    cost_total: float
    status: str
    amount_paid: float
    notes: Optional[str]
    items: list[SaleItemOut] = []
    payments: list[PaymentOut] = []

    class Config:
        from_attributes = True
