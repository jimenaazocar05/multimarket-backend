from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import asc
from uuid import UUID
from app.db import get_db
from app.auth.dependencies import get_current_user
from app.models.product import Product
from app.models.inventory_movement import InventoryMovement
from app.schemas.product import ProductCreate, ProductUpdate, ProductOut

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("", response_model=list[ProductOut])
def list_products(
    active: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    query = db.query(Product)
    if active is not None:
        query = query.filter(Product.active == active)
    return query.order_by(asc(Product.name)).all()


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: UUID, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(404, "Producto no encontrado")
    return product


@router.post("", response_model=ProductOut, status_code=201)
def create_product(payload: ProductCreate, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    try:
        product = Product(**payload.model_dump())
        db.add(product)
        db.flush()  # asigna product.id sin cerrar la transacción

        if payload.stock > 0:
            db.add(InventoryMovement(
                product_id=product.id,
                movement_type="initial",
                quantity_change=payload.stock,
                reference_id=None,
                notes="Stock inicial al crear el producto",
            ))

        db.commit()
        db.refresh(product)
        return product
    except Exception:
        db.rollback()
        raise


@router.put("/{product_id}", response_model=ProductOut)
def update_product(product_id: UUID, payload: ProductUpdate, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(404, "Producto no encontrado")
    for field, value in payload.model_dump().items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product
