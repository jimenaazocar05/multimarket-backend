from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from uuid import UUID
from app.db import get_db
from app.auth.dependencies import get_current_user
from app.models.product import Product
from app.models.inventory_movement import InventoryMovement
from app.schemas.inventory import StockAdjustment, InventoryMovementOut
from app.schemas.product import ProductOut

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


@router.post("/adjust", response_model=ProductOut)
def adjust_stock(payload: StockAdjustment, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    # Bloqueo de fila — mismo motivo que en Etapa 3: evita que un ajuste
    # y una venta simultánea sobre el mismo producto se pisen entre sí.
    product = (
        db.query(Product)
        .filter(Product.id == payload.product_id)
        .with_for_update()
        .first()
    )
    if not product:
        raise HTTPException(404, "Producto no encontrado")

    change = payload.new_stock - float(product.stock)

    if change == 0:
        # No hay nada que ajustar; devolver el producto sin crear un
        # movimiento vacío que ensuciaría el historial.
        return product

    try:
        product.stock = payload.new_stock
        db.add(InventoryMovement(
            product_id=product.id,
            movement_type="adjustment",
            quantity_change=change,
            reference_id=None,
            notes=payload.notes,
        ))
        db.commit()
        db.refresh(product)
        return product
    except Exception:
        db.rollback()
        raise


@router.get("/movements", response_model=list[InventoryMovementOut])
def list_movements(
    product_id: UUID = Query(...),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    return (
        db.query(InventoryMovement)
        .filter(InventoryMovement.product_id == product_id)
        .order_by(InventoryMovement.created_at.desc())
        .limit(50)
        .all()
    )
