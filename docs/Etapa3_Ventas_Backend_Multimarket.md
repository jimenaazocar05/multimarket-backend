# Plan de implementación — Etapa 3: El núcleo transaccional — Ventas

**Objetivo de la etapa:** implementar `POST /api/sales` como una transacción atómica real que afecta 4 tablas (`sales`, `sale_items`, `products`, `inventory_movements`), con las validaciones que hoy no existen porque la lógica vive sin protección en el navegador. Esta es la operación más crítica de todo el sistema: si algo falla a mitad de camino, **nada** debe quedar aplicado.

**Requisito previo:** Etapas 1 y 2 completadas y verificadas.

---

## Paso 1 — Por qué esta etapa es distinta a las anteriores

En las Etapas 1 y 2 cada endpoint tocaba una sola tabla por operación. Aquí una sola venta tiene que:

1. Insertar 1 fila en `sales`.
2. Insertar N filas en `sale_items` (una por producto vendido).
3. Descontar `stock` en `products` para cada producto vendido.
4. Insertar N filas en `inventory_movements` (una por producto, registrando la salida).

Si el paso 3 falla en el segundo producto (por ejemplo, por una condición de carrera de stock), **los pasos 1, 2 y el 3 del primer producto deben revertirse**. Esto solo se garantiza con una transacción de base de datos explícita, no con llamadas sueltas como hace hoy `data.ts` en el frontend.

---

## Paso 2 — Modelos nuevos: `sale_items` e `inventory_movements`

```python
# app/models/sale_item.py
from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.db import Base

class SaleItem(Base):
    __tablename__ = "sale_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sale_id = Column(UUID(as_uuid=True), ForeignKey("sales.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    product_name = Column(String, nullable=False)
    quantity = Column(Numeric(12, 2), nullable=False)
    unit_price = Column(Numeric(12, 2), nullable=False)
    unit_cost = Column(Numeric(12, 2), nullable=False, default=0)
    subtotal = Column(Numeric(12, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

```python
# app/models/inventory_movement.py
from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.db import Base

class InventoryMovement(Base):
    __tablename__ = "inventory_movements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    movement_type = Column(String, nullable=False)  # 'sale' | 'purchase' | 'adjustment' | 'initial'
    quantity_change = Column(Numeric(12, 2), nullable=False)  # negativo = salida, positivo = entrada
    reference_id = Column(UUID(as_uuid=True), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

---

## Paso 3 — Schemas Pydantic

```python
# app/schemas/sale.py
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal
from uuid import UUID
from datetime import datetime

class SaleItemIn(BaseModel):
    product_id: UUID
    product_name: str
    quantity: float = Field(gt=0)
    unit_price: float = Field(ge=0)
    unit_cost: float = Field(ge=0)

class SaleCreate(BaseModel):
    customer_id: Optional[UUID] = None
    customer_name: Optional[str] = None
    status: Literal["paid", "credit"]
    notes: Optional[str] = None
    items: list[SaleItemIn]

    @field_validator("items")
    @classmethod
    def at_least_one_item(cls, v):
        if not v:
            raise ValueError("La venta debe tener al menos un producto")
        return v

class SaleItemOut(BaseModel):
    id: UUID
    product_id: Optional[UUID]
    product_name: str
    quantity: float
    unit_price: float
    unit_cost: float
    subtotal: float

    class Config:
        from_attributes = True

class SaleOut(BaseModel):
    id: UUID
    sale_date: datetime
    customer_id: Optional[UUID]
    customer_name: Optional[str]
    total: float
    cost_total: float
    status: str
    amount_paid: float
    notes: Optional[str]
    items: list[SaleItemOut] = []

    class Config:
        from_attributes = True
```

La validación `status === 'credit' → customer_id obligatorio` y la de `quantity > 0` / `unit_price >= 0` quedan resueltas a nivel de schema — la petición ni siquiera llega a la lógica de negocio si viene mal formada. La validación de **stock suficiente**, en cambio, necesita leer la base de datos, así que va en el router.

---

## Paso 4 — El endpoint transaccional

```python
# app/routers/sales.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import asc
from datetime import date, datetime
from uuid import UUID
from app.db import get_db
from app.auth.dependencies import get_current_user
from app.models.sale import Sale
from app.models.sale_item import SaleItem
from app.models.product import Product
from app.models.inventory_movement import InventoryMovement
from app.schemas.sale import SaleCreate, SaleOut

router = APIRouter(prefix="/api/sales", tags=["sales"])

@router.post("", response_model=SaleOut, status_code=201)
def create_sale(payload: SaleCreate, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
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
        sale = Sale(
            customer_id=payload.customer_id,
            customer_name=payload.customer_name,
            total=total,
            cost_total=cost_total,
            status=payload.status,
            amount_paid=amount_paid,
            notes=payload.notes,
        )
        db.add(sale)
        db.flush()  # asigna sale.id sin cerrar la transacción

        # 4. Insertar items, descontar stock, registrar movimientos
        for item in payload.items:
            subtotal = item.quantity * item.unit_price
            db.add(SaleItem(
                sale_id=sale.id,
                product_id=item.product_id,
                product_name=item.product_name,
                quantity=item.quantity,
                unit_price=item.unit_price,
                unit_cost=item.unit_cost,
                subtotal=subtotal,
            ))

            product = products_by_id[str(item.product_id)]
            product.stock = product.stock - item.quantity

            db.add(InventoryMovement(
                product_id=item.product_id,
                movement_type="sale",
                quantity_change=-item.quantity,
                reference_id=sale.id,
                notes=f"Venta #{sale.id}",
            ))

        db.commit()
        db.refresh(sale)
        return sale

    except Exception:
        db.rollback()
        raise
```

**Puntos clave de esta implementación:**

- **`with_for_update()`** bloquea la fila del producto hasta que la transacción termina — si dos ventas intentan vender el último producto en simultáneo, la segunda espera a que la primera termine y ve el stock ya actualizado, en vez de que ambas lean "stock: 1" y ambas lo descuenten.
- La validación de stock ocurre **antes** de cualquier `INSERT`, así que si falla, no hay nada que revertir.
- `db.flush()` en vez de `db.commit()` después de crear `sale` — esto asigna el `id` autogenerado sin cerrar la transacción, necesario porque `sale_items` e `inventory_movements` lo referencian.
- El `try/except` con `db.rollback()` es la red de seguridad: cualquier error inesperado (de red, de constraint, lo que sea) revierte **todo** lo que se había insertado en esta transacción, incluyendo el `flush` de `sale`.
- No hay `db.commit()` intermedio en ningún punto del bucle — todo se confirma junto al final, o nada se confirma.

---

## Paso 5 — Endpoints de lectura

```python
# agregar al mismo router
from fastapi import Query
from datetime import date as date_type

@router.get("", response_model=list[SaleOut])
def list_sales(
    from_: date_type | None = Query(default=None, alias="from"),
    to: date_type | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    query = db.query(Sale)
    if from_:
        query = query.filter(Sale.sale_date >= from_)
    if to:
        query = query.filter(Sale.sale_date <= to)
    if status:
        query = query.filter(Sale.status == status)
    return query.order_by(Sale.sale_date.desc()).all()

@router.get("/{sale_id}/items", response_model=list[SaleItemOut])
def sale_items(sale_id: UUID, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    sale = db.query(Sale).filter(Sale.id == sale_id).first()
    if not sale:
        raise HTTPException(404, "Venta no encontrada")
    return db.query(SaleItem).filter(SaleItem.product_id.isnot(None), SaleItem.sale_id == sale_id).all()
```

`GET /api/sales?status=credit` reutiliza el mismo endpoint de listado — es lo que usarán el Dashboard y la futura pantalla de `/receivables` en la Etapa 5.

---

## Paso 6 — Registrar el router

```python
# app/main.py
from app.routers import sales
app.include_router(sales.router)
```

---

## Paso 7 — Casos de prueba obligatorios antes de dar por cerrada la etapa

Estos son los casos que hoy el frontend **no** puede garantizar por sí solo, y que justifican por qué esta lógica se mueve al backend:

1. **Venta normal exitosa** — 2-3 productos con stock suficiente, `status: 'paid'` → verificar que `sales`, `sale_items`, `products.stock` y `inventory_movements` quedan correctos.
2. **Venta a crédito sin `customer_id`** → debe rechazar con 422 antes de tocar la base de datos.
3. **Venta con stock insuficiente en el segundo producto del carrito** → verificar que **ningún** producto del carrito quedó con el stock descontado (ni siquiera el primero, que sí tenía stock suficiente) y que no se creó la fila en `sales`.
4. **Dos ventas simultáneas del mismo producto con stock justo para una sola** — simular con dos requests concurrentes (ej. con `httpx` async o dos terminales) y confirmar que una tiene éxito y la otra se rechaza por stock insuficiente, sin que el stock quede negativo.
5. **Producto inexistente en el carrito** → 404 antes de insertar nada.
6. **`GET /api/sales?status=credit`** → debe devolver exactamente las ventas fiadas, en el mismo formato que usará `/receivables` en la Etapa 5.

---

## Checklist de salida de la etapa

- [ ] `POST /api/sales` corre dentro de una transacción real (no llamadas sueltas)
- [ ] Bloqueo de fila (`with_for_update`) previene condiciones de carrera en stock
- [ ] Validación de carrito no vacío y `customer_id` obligatorio en crédito, resuelta en el schema
- [ ] Validación de stock suficiente por producto, resuelta en el router antes de escribir
- [ ] Un error a mitad de la transacción no deja registros parciales en ninguna de las 4 tablas
- [ ] `GET /api/sales` con filtros por fecha y status funcionando
- [ ] `GET /api/sales/:id/items` funcionando
- [ ] Los 6 casos de prueba del Paso 7 verificados manualmente

Con esto el POS puede migrar de `data.ts` (ejecutándose sin protección en el navegador) a este endpoint, eliminando el riesgo de ventas con stock inconsistente. La Etapa 4 reutiliza el mismo patrón transaccional para los ajustes manuales de inventario.
