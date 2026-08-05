from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from datetime import date
from uuid import UUID
from app.db import get_db
from app.models.payable import Payable
from app.models.payment import Payment
from app.models.product import Product
from app.models.purchase_item import PurchaseItem
from app.models.inventory_movement import InventoryMovement
from app.schemas.finance import PayableCreate, PayablePay, PayableOut, PurchaseCreate

router = APIRouter(prefix="/api/payables", tags=["payables"])


def _to_out(
    p: Payable,
    payments: list[Payment] | None = None,
    items: list[PurchaseItem] | None = None,
) -> PayableOut:
    today = date.today()
    balance = float(p.amount - p.amount_paid)
    return PayableOut(
        id=p.id, supplier_id=p.supplier_id, supplier_name=p.supplier_name,
        concept=p.concept, amount=float(p.amount), amount_paid=float(p.amount_paid),
        balance=balance, due_date=p.due_date, issue_date=p.issue_date,
        days_old=(today - p.issue_date).days if p.issue_date else 0,
        overdue=bool(p.due_date and p.due_date < today and balance > 0),
        payments=payments or [],
        items=items or [],
    )


@router.get("", response_model=list[PayableOut])
def list_payables(
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = Query(default=None),
    db: Session = Depends(get_db)
):
    query = db.query(Payable)
    if from_:
        query = query.filter(Payable.issue_date >= from_)
    if to:
        query = query.filter(Payable.issue_date <= to)
    
    payables = query.order_by(Payable.issue_date.desc()).all()
    
    # Pre-cargar items manualmente (similar a como lo hace get_payable)
    if payables:
        payable_ids = [p.id for p in payables]
        all_items = db.query(PurchaseItem).filter(PurchaseItem.payable_id.in_(payable_ids)).all()
        items_by_payable = {}
        for item in all_items:
            items_by_payable.setdefault(item.payable_id, []).append(item)
            
        return [_to_out(p, items=items_by_payable.get(p.id, [])) for p in payables]
    
    return []


@router.get("/{payable_id}", response_model=PayableOut)
def get_payable(payable_id: UUID, db: Session = Depends(get_db)):
    payable = db.query(Payable).filter(Payable.id == payable_id).first()
    if not payable:
        raise HTTPException(404, "Cuenta por pagar no encontrada")
    payments = (
        db.query(Payment)
        .filter(Payment.payable_id == payable_id, Payment.kind == "payable")
        .order_by(Payment.payment_date.asc(), Payment.created_at.asc())
        .all()
    )
    items = (
        db.query(PurchaseItem)
        .filter(PurchaseItem.payable_id == payable_id)
        .order_by(PurchaseItem.created_at.asc())
        .all()
    )
    return _to_out(payable, payments, items)


@router.post("", response_model=PayableOut, status_code=201)
def create_payable(payload: PayableCreate, db: Session = Depends(get_db)):
    payable = Payable(**payload.model_dump())
    db.add(payable)
    db.commit()
    db.refresh(payable)
    return _to_out(payable)


@router.post("/purchase", response_model=PayableOut, status_code=201)
def create_purchase(payload: PurchaseCreate, db: Session = Depends(get_db)):
    # Bloquear los productos ANTES de escribir nada, mismo motivo que en
    # create_sale: evita que una compra y otra operación sobre el mismo
    # producto se pisen entre sí.
    products_by_id = {}
    for item in payload.items:
        product = (
            db.query(Product)
            .filter(Product.id == item.product_id)
            .with_for_update()
            .first()
        )
        if not product:
            raise HTTPException(404, f"Producto {item.product_id} no encontrado")
        products_by_id[str(item.product_id)] = product

    total = sum(i.quantity * i.unit_cost for i in payload.items)

    try:
        payable_kwargs = dict(
            supplier_id=payload.supplier_id,
            supplier_name=payload.supplier_name,
            concept=payload.concept,
            amount=total,
            amount_paid=total if payload.is_cash else 0,
            due_date=None if payload.is_cash else payload.due_date,
            notes=payload.notes,
        )
        if payload.issue_date:
            payable_kwargs["issue_date"] = payload.issue_date
        payable = Payable(**payable_kwargs)
        db.add(payable)
        db.flush()  # asigna payable.id sin cerrar la transacción

        if payload.is_cash and total > 0:
            db.add(Payment(
                kind="payable",
                payable_id=payable.id,
                amount=total,
                payment_date=payload.issue_date or date.today(),
            ))

        purchase_items = []
        for item in payload.items:
            subtotal = item.quantity * item.unit_cost
            purchase_item = PurchaseItem(
                payable_id=payable.id,
                product_id=item.product_id,
                product_name=item.product_name,
                quantity=item.quantity,
                unit_cost=item.unit_cost,
                subtotal=subtotal,
            )
            db.add(purchase_item)
            purchase_items.append(purchase_item)

            product = products_by_id[str(item.product_id)]
            product.stock = float(product.stock) + item.quantity
            product.cost = item.unit_cost  # el costo se actualiza al de la última compra

            db.add(InventoryMovement(
                product_id=item.product_id,
                movement_type="purchase",
                quantity_change=item.quantity,
                reference_id=payable.id,
                notes=f"Compra #{payable.id}",
            ))

        db.commit()
        db.refresh(payable)
        return _to_out(payable, items=purchase_items)

    except Exception:
        db.rollback()
        raise


@router.post("/pay", response_model=PayableOut)
def pay_payable(payload: PayablePay, db: Session = Depends(get_db)):
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
        payable.amount_paid = float(payable.amount_paid) + payload.amount
        db.commit()
        db.refresh(payable)
    except Exception:
        db.rollback()
        raise

    return _to_out(payable)
