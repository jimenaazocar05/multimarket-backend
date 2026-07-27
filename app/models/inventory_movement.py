from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.db import Base


class InventoryMovement(Base):
    __tablename__ = "inventory_movements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    movement_type = Column(String, nullable=False)  # 'sale' | 'purchase' | 'adjustment' | 'initial'
    quantity_change = Column(Numeric(12, 2), nullable=False)  # negativo = salida, positivo = entrada
    reference_id = Column(UUID(as_uuid=True), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
