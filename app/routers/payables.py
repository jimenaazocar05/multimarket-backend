from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date
from app.db import get_db
from app.auth.dependencies import get_current_user
from app.models.payable import Payable
from app.models.payment import Payment
from app.schemas.finance import PayableCreate, PayablePay, PayableOut

router = APIRouter(prefix="/api/payables", tags=["payables"])


def _to_out(p: Payable) -> PayableOut:
    today = date.today()
    balance = float(p.amount - p.amount_paid)
    return PayableOut(
        id=p.id, supplier_id=p.supplier_id, supplier_name=p.supplier_name,
        concept=p.concept, amount=float(p.amount), amount_paid=float(p.amount_paid),
        balance=balance, due_date=p.due_date, issue_date=p.issue_date,
        days_old=(today - p.issue_date).days,
        overdue=bool(p.due_date and p.due_date < today and balance > 0),
    )


@router.get("", response_model=list[PayableOut])
def list_payables(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    payables = db.query(Payable).order_by(Payable.issue_date.desc()).all()
    return [_to_out(p) for p in payables]


@router.post("", response_model=PayableOut, status_code=201)
def create_payable(payload: PayableCreate, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    payable = Payable(**payload.model_dump())
    db.add(payable)
    db.commit()
    db.refresh(payable)
    return _to_out(payable)


@router.post("/pay", response_model=PayableOut)
def pay_payable(payload: PayablePay, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    payable = (
        db.query(Payable)
        .filter(Payable.id == payload.payable_id)
        .with_for_update()
        .first()
    )
    if not payable:
        raise HTTPException(404, "Cuenta por pagar no encontrada")

    balance = float(payable.amount - payable.amount_paid)
    if payload.amount > balance:
        raise HTTPException(422, f"El pago ({payload.amount}) excede el saldo pendiente ({balance})")

    try:
        db.add(Payment(kind="payable", payable_id=payable.id, amount=payload.amount))
        payable.amount_paid = payable.amount_paid + payload.amount
        db.commit()
        db.refresh(payable)
    except Exception:
        db.rollback()
        raise

    return _to_out(payable)
