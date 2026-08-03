from pydantic import BaseModel, Field, field_validator
from typing import Optional
from uuid import UUID
from datetime import date, datetime


class ReceivablePay(BaseModel):
    sale_id: UUID
    amount: float = Field(gt=0)


class PayableCreate(BaseModel):
    supplier_id: Optional[UUID] = None
    supplier_name: Optional[str] = None
    concept: str
    amount: float = Field(gt=0)
    due_date: Optional[date] = None
    notes: Optional[str] = None


class PayablePay(BaseModel):
    payable_id: UUID
    amount: float = Field(gt=0)


class ReceivableOut(BaseModel):
    id: UUID
    sale_date: datetime
    customer_id: Optional[UUID]
    customer_name: Optional[str]
    total: float
    amount_paid: float
    balance: float
    days_old: int


class PaymentOut(BaseModel):
    id: UUID
    amount: float
    payment_date: date
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class PurchaseItemIn(BaseModel):
    product_id: UUID
    product_name: str
    quantity: float = Field(gt=0)
    unit_cost: float = Field(ge=0)


class PurchaseCreate(BaseModel):
    supplier_id: Optional[UUID] = None
    supplier_name: Optional[str] = None
    concept: str = "Compra de mercancía"
    due_date: Optional[date] = None
    notes: Optional[str] = None
    items: list[PurchaseItemIn]

    @field_validator("items")
    @classmethod
    def at_least_one_item(cls, v):
        if not v:
            raise ValueError("La compra debe tener al menos un producto")
        return v


class PurchaseItemOut(BaseModel):
    id: UUID
    product_id: Optional[UUID]
    product_name: str
    quantity: float
    unit_cost: float
    subtotal: float

    class Config:
        from_attributes = True


class PayableOut(BaseModel):
    id: UUID
    supplier_id: Optional[UUID]
    supplier_name: Optional[str]
    concept: str
    amount: float
    amount_paid: float
    balance: float
    due_date: Optional[date]
    issue_date: date
    days_old: int
    overdue: bool
    payments: list[PaymentOut] = []
    items: list[PurchaseItemOut] = []
