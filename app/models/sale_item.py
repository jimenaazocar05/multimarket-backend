from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.db import Base


class SaleItem(Base):
    __tablename__ = "sale_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sale_id = Column(UUID(as_uuid=True), ForeignKey("sales.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    product_name = Column(String, nullable=False)
    quantity = Column(Numeric(12, 2), nullable=False)
    unit_price = Column(Numeric(12, 2), nullable=False)
    unit_cost = Column(Numeric(12, 2), nullable=False, default=0)
    subtotal = Column(Numeric(12, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
