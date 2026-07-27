from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date
from app.db import get_db
from app.auth.dependencies import get_current_user
from app.models.sale import Sale
from app.models.sale_item import SaleItem
from app.schemas.dashboard import TopProduct, ReportsOut

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("", response_model=ReportsOut)
def get_reports(
    from_: date = Query(..., alias="from"),
    to: date = Query(...),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    totals = (
        db.query(
            func.coalesce(func.sum(Sale.total), 0).label("total_sales"),
            func.coalesce(func.sum(Sale.cost_total), 0).label("total_cost"),
        )
        .filter(Sale.sale_date >= from_, Sale.sale_date <= to)
        .first()
    )
    total_sales = float(totals.total_sales)
    total_cost = float(totals.total_cost)

    base_query = (
        db.query(
            SaleItem.product_id,
            SaleItem.product_name,
            func.sum(SaleItem.subtotal).label("revenue"),
            func.sum(SaleItem.subtotal - (SaleItem.unit_cost * SaleItem.quantity)).label("profit"),
            func.sum(SaleItem.quantity).label("quantity"),
        )
        .join(Sale, Sale.id == SaleItem.sale_id)
        .filter(Sale.sale_date >= from_, Sale.sale_date <= to)
        .group_by(SaleItem.product_id, SaleItem.product_name)
    )

    top_by_revenue = [
        TopProduct(product_id=r.product_id, product_name=r.product_name,
                   revenue=float(r.revenue), profit=float(r.profit), quantity=float(r.quantity))
        for r in base_query.order_by(func.sum(SaleItem.subtotal).desc()).limit(15).all()
    ]
    top_by_profit = [
        TopProduct(product_id=r.product_id, product_name=r.product_name,
                   revenue=float(r.revenue), profit=float(r.profit), quantity=float(r.quantity))
        for r in base_query.order_by(
            (func.sum(SaleItem.subtotal - (SaleItem.unit_cost * SaleItem.quantity))).desc()
        ).limit(15).all()
    ]

    return ReportsOut(
        total_sales=total_sales,
        total_cost=total_cost,
        total_profit=total_sales - total_cost,
        top_by_revenue=top_by_revenue,
        top_by_profit=top_by_profit,
    )
