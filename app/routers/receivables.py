from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date
from app.db import get_db
from app.models.sale import Sale
from app.models.payment import Payment
from app.schemas.finance import ReceivablePay, ReceivableOut

router = APIRouter(prefix="/api/receivables", tags=["receivables"])


@router.get("", response_model=list[ReceivableOut])
def list_receivables(db: Session = Depends(get_db)):
    sales = (
        db.query(Sale)
        .filter(Sale.status == "credit")
        .filter(Sale.total > Sale.amount_paid)
        .order_by(Sale.sale_date.asc())
        .all()
    )
    today = date.today()
    return [
        ReceivableOut(
            id=s.id,
            sale_date=s.sale_date,
            customer_id=s.customer_id,
            customer_name=s.customer_name,
            total=float(s.total),
            amount_paid=float(s.amount_paid),
            balance=float(s.total - s.amount_paid),
            days_old=(today - s.sale_date.date()).days,
        )
        for s in sales
    ]


@router.post("/pay", response_model=ReceivableOut)
def pay_receivable(payload: ReceivablePay, db: Session = Depends(get_db)):
    # Bloqueo de fila — dos abonos simultáneos a la misma venta
    # no deben pisarse ni sobrepasar el saldo juntos.
    sale = (
        db.query(Sale)
        .filter(Sale.id == payload.sale_id)
        .with_for_update()
        .first()
    )
    if not sale:
        raise HTTPException(404, "Venta no encontrada")

    balance = float(sale.total - sale.amount_paid)
    if payload.amount > balance:
        raise HTTPException(422, f"El abono ({payload.amount}) excede el saldo pendiente ({balance})")

    try:
        db.add(Payment(kind="receivable", sale_id=sale.id, amount=payload.amount))
        sale.amount_paid = float(sale.amount_paid) + payload.amount
        if sale.amount_paid >= sale.total:
            sale.status = "paid"
        db.commit()
        db.refresh(sale)
    except Exception:
        db.rollback()
        raise

    today = date.today()
    return ReceivableOut(
        id=sale.id, sale_date=sale.sale_date, customer_id=sale.customer_id,
        customer_name=sale.customer_name, total=float(sale.total),
        amount_paid=float(sale.amount_paid), balance=float(sale.total - sale.amount_paid),
        days_old=(today - sale.sale_date.date()).days,
    )
