from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import cast, Date
from datetime import date as date_type
from uuid import UUID
from app.db import get_db
from app.models.sale import Sale
from app.models.sale_item import SaleItem
from app.models.product import Product
from app.models.inventory_movement import InventoryMovement
from app.models.payment import Payment
from app.schemas.sale import SaleCreate, SaleOut, SaleItemOut

router = APIRouter(prefix="/api/sales", tags=["sales"])


@router.post("", response_model=SaleOut, status_code=201)
def create_sale(payload: SaleCreate, db: Session = Depends(get_db)):
    if payload.status == "credit" and payload.customer_id is None:
        raise HTTPException(422, "customer_id es obligatorio para ventas a crédito")

    # 1. Bloquear y validar stock de cada producto ANTES de escribir nada.
    #    SELECT ... FOR UPDATE evita condiciones de carrera si dos ventas
    #    del mismo producto llegan casi al mismo tiempo.
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
        if product.stock < item.quantity:
            raise HTTPException(
                422,
                f"Stock insuficiente para '{product.name}': disponible {product.stock}, solicitado {item.quantity}",
            )
        products_by_id[str(item.product_id)] = product

    # 2. Calcular totales
    total = sum(i.quantity * i.unit_price for i in payload.items)
    cost_total = sum(i.quantity * i.unit_cost for i in payload.items)
    amount_paid = total if payload.status == "paid" else 0

    try:
        # 3. Insertar la venta
        sale_kwargs = dict(
            customer_id=payload.customer_id,
            customer_name=payload.customer_name,
            total=total,
            cost_total=cost_total,
            status=payload.status,
            amount_paid=amount_paid,
            notes=payload.notes,
        )
        if payload.sale_date:
            sale_kwargs["sale_date"] = payload.sale_date
        sale = Sale(**sale_kwargs)
        db.add(sale)
        db.flush()  # asigna sale.id sin cerrar la transacción

        # 4. Insertar items, descontar stock, registrar movimientos
        sale_items = []
        for item in payload.items:
            subtotal = item.quantity * item.unit_price
            sale_item = SaleItem(
                sale_id=sale.id,
                product_id=item.product_id,
                product_name=item.product_name,
                quantity=item.quantity,
                unit_price=item.unit_price,
                unit_cost=item.unit_cost,
                subtotal=subtotal,
            )
            db.add(sale_item)
            sale_items.append(sale_item)

            product = products_by_id[str(item.product_id)]
            product.stock = float(product.stock) - item.quantity

            db.add(InventoryMovement(
                product_id=item.product_id,
                movement_type="sale",
                quantity_change=-item.quantity,
                reference_id=sale.id,
                notes=f"Venta #{sale.id}",
            ))

        db.commit()
        db.refresh(sale)

        # Cargar items para la respuesta
        sale.items = sale_items
        return sale

    except Exception:
        db.rollback()
        raise


@router.get("", response_model=list[SaleOut])
def list_sales(
    from_: date_type | None = Query(default=None, alias="from"),
    to: date_type | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(Sale)
    if from_:
        query = query.filter(cast(Sale.sale_date, Date) >= from_)
    if to:
        query = query.filter(cast(Sale.sale_date, Date) <= to)
    if status:
        query = query.filter(Sale.status == status)
    return query.order_by(Sale.sale_date.desc()).all()


@router.get("/{sale_id}", response_model=SaleOut)
def get_sale(sale_id: UUID, db: Session = Depends(get_db)):
    sale = db.query(Sale).filter(Sale.id == sale_id).first()
    if not sale:
        raise HTTPException(404, "Venta no encontrada")
    sale.items = db.query(SaleItem).filter(SaleItem.sale_id == sale_id).all()
    sale.payments = (
        db.query(Payment)
        .filter(Payment.sale_id == sale_id, Payment.kind == "receivable")
        .order_by(Payment.payment_date.asc(), Payment.created_at.asc())
        .all()
    )
    return sale


@router.get("/{sale_id}/items", response_model=list[SaleItemOut])
def sale_items(sale_id: UUID, db: Session = Depends(get_db)):
    sale = db.query(Sale).filter(Sale.id == sale_id).first()
    if not sale:
        raise HTTPException(404, "Venta no encontrada")
    return db.query(SaleItem).filter(SaleItem.sale_id == sale_id).all()
