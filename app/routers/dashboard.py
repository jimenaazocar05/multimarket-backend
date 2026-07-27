from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, timedelta
from app.db import get_db
from app.auth.dependencies import get_current_user
from app.models.sale import Sale
from app.models.sale_item import SaleItem
from app.models.product import Product
from app.models.customer import Customer
from app.schemas.dashboard import DashboardOut, TopProduct, LowStockProduct

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardOut)
def get_dashboard(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    def sum_total(since):
        return float(
            db.query(func.coalesce(func.sum(Sale.total), 0))
            .filter(Sale.sale_date >= since)
            .scalar()
        )

    day_total = sum_total(today)
    week_total = sum_total(week_start)
    month_total = sum_total(month_start)

    month_profit = float(
        db.query(func.coalesce(func.sum(Sale.total - Sale.cost_total), 0))
        .filter(Sale.sale_date >= month_start)
        .scalar()
    )

    top_rows = (
        db.query(
            SaleItem.product_id,
            SaleItem.product_name,
            func.sum(SaleItem.subtotal).label("revenue"),
            func.sum(SaleItem.subtotal - (SaleItem.unit_cost * SaleItem.quantity)).label("profit"),
            func.sum(SaleItem.quantity).label("quantity"),
        )
        .join(Sale, Sale.id == SaleItem.sale_id)
        .filter(Sale.sale_date >= month_start)
        .group_by(SaleItem.product_id, SaleItem.product_name)
        .order_by(func.sum(SaleItem.subtotal).desc())
        .limit(10)
        .all()
    )
    top_products = [
        TopProduct(
            product_id=r.product_id, product_name=r.product_name,
            revenue=float(r.revenue), profit=float(r.profit), quantity=float(r.quantity),
        )
        for r in top_rows
    ]

    low_stock_rows = (
        db.query(Product)
        .filter(Product.active.is_(True))
        .filter(Product.stock <= Product.low_stock_threshold)
        .order_by(Product.stock.asc())
        .all()
    )
    low_stock = [
        LowStockProduct(id=p.id, name=p.name, stock=float(p.stock), low_stock_threshold=float(p.low_stock_threshold))
        for p in low_stock_rows
    ]

    open_receivables = float(
        db.query(func.coalesce(func.sum(Sale.total - Sale.amount_paid), 0))
        .filter(Sale.status == "credit")
        .scalar()
    )

    customer_count = db.query(func.count(Customer.id)).scalar()

    return DashboardOut(
        day_total=day_total,
        week_total=week_total,
        month_total=month_total,
        month_profit=month_profit,
        top_products=top_products,
        low_stock=low_stock,
        open_receivables=open_receivables,
        customer_count=customer_count,
    )
