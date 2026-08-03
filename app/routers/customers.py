from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from uuid import UUID
from app.db import get_db
from app.models.customer import Customer
from app.models.sale import Sale
from app.schemas.customer import CustomerCreate, CustomerOut

router = APIRouter(prefix="/api/customers", tags=["customers"])


def _agg_subquery(db: Session):
    return (
        db.query(
            Sale.customer_id.label("customer_id"),
            func.coalesce(func.sum(Sale.total), 0).label("total"),
            func.coalesce(
                func.sum(case((Sale.status == "credit", Sale.total - Sale.amount_paid), else_=0)),
                0,
            ).label("owed"),
            func.count(Sale.id).label("count"),
        )
        .group_by(Sale.customer_id)
        .subquery()
    )


@router.get("", response_model=list[CustomerOut])
def list_customers(db: Session = Depends(get_db)):
    agg = _agg_subquery(db)
    rows = (
        db.query(Customer, agg.c.total, agg.c.owed, agg.c.count)
        .outerjoin(agg, agg.c.customer_id == Customer.id)
        .order_by(Customer.name)
        .all()
    )
    result = []
    for customer, total, owed, count in rows:
        result.append(
            CustomerOut(
                **{k: getattr(customer, k) for k in ["id", "name", "phone", "notes", "created_at", "updated_at"]},
                agg={"total": float(total or 0), "owed": float(owed or 0), "count": int(count or 0)},
            )
        )
    return result


@router.get("/{customer_id}/sales")
def customer_sales(customer_id: UUID, db: Session = Depends(get_db)):
    return (
        db.query(Sale)
        .filter(Sale.customer_id == customer_id)
        .order_by(Sale.sale_date.desc())
        .all()
    )


@router.post("", status_code=201)
def create_customer(payload: CustomerCreate, db: Session = Depends(get_db)):
    customer = Customer(**payload.model_dump())
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


@router.put("/{customer_id}")
def update_customer(customer_id: UUID, payload: CustomerCreate, db: Session = Depends(get_db)):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(404, "Cliente no encontrado")
    for field, value in payload.model_dump().items():
        setattr(customer, field, value)
    db.commit()
    db.refresh(customer)
    return customer
