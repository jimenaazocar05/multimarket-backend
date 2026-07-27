from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime


class StockAdjustment(BaseModel):
    product_id: UUID
    new_stock: float = Field(ge=0, description="Nuevo valor absoluto de stock, no un delta")
    notes: Optional[str] = None


class InventoryMovementOut(BaseModel):
    id: UUID
    product_id: UUID
    movement_type: str
    quantity_change: float
    reference_id: Optional[UUID]
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
