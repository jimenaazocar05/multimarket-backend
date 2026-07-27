from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from uuid import UUID
from app.db import get_db
from app.auth.dependencies import get_current_user
from app.models.supplier import Supplier
from app.models.payable import Payable
from app.schemas.supplier import SupplierCreate

router = APIRouter(prefix="/api/suppliers", tags=["suppliers"])


def _agg_subquery(db: Session):
    return (
        db.query(
            Payable.supplier_id.label("supplier_id"),
            func.coalesce(func.sum(Payable.amount), 0).label("total"),
            func.coalesce(func.sum(Payable.amount - Payable.amount_paid), 0).label("owed"),
            func.count(Payable.id).label("count"),
        )
        .group_by(Payable.supplier_id)
        .subquery()
    )


@router.get("")
def list_suppliers(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    agg = _agg_subquery(db)
    rows = (
        db.query(Supplier, agg.c.total, agg.c.owed, agg.c.count)
        .outerjoin(agg, agg.c.supplier_id == Supplier.id)
        .order_by(Supplier.name)
        .all()
    )
    return [
        {
            "id": s.id, "name": s.name, "phone": s.phone, "notes": s.notes,
            "agg": {"total": float(total or 0), "owed": float(owed or 0), "count": int(count or 0)},
        }
        for s, total, owed, count in rows
    ]


@router.post("", status_code=201)
def create_supplier(payload: SupplierCreate, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    supplier = Supplier(**payload.model_dump())
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier


@router.put("/{supplier_id}")
def update_supplier(supplier_id: UUID, payload: SupplierCreate, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(404, "Proveedor no encontrado")
    for field, value in payload.model_dump().items():
        setattr(supplier, field, value)
    db.commit()
    db.refresh(supplier)
    return supplier
