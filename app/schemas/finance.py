from pydantic import BaseModel, Field
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
