from pydantic import BaseModel
from typing import Optional
from uuid import UUID


class TopProduct(BaseModel):
    product_id: Optional[UUID]
    product_name: str
    revenue: float
    profit: float
    quantity: float


class LowStockProduct(BaseModel):
    id: UUID
    name: str
    stock: float
    low_stock_threshold: float


class DashboardOut(BaseModel):
    day_total: float
    week_total: float
    month_total: float
    month_profit: float
    top_products: list[TopProduct]
    low_stock: list[LowStockProduct]
    open_receivables: float
    customer_count: int


class ReportsOut(BaseModel):
    total_sales: float
    total_cost: float
    total_profit: float
    top_by_revenue: list[TopProduct]
    top_by_profit: list[TopProduct]
