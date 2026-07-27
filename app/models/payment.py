from sqlalchemy import Column, String, Numeric, Date, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.db import Base


class Payment(Base):
    __tablename__ = "payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind = Column(String, nullable=False)  # 'receivable' | 'payable'
    sale_id = Column(UUID(as_uuid=True), ForeignKey("sales.id", ondelete="CASCADE"), nullable=True)
    payable_id = Column(UUID(as_uuid=True), ForeignKey("payables.id", ondelete="CASCADE"), nullable=True)
    amount = Column(Numeric(12, 2), nullable=False)
    payment_date = Column(Date, server_default=func.current_date())
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
