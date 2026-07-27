# Plan de implementación — Etapa 4: Inventario — Ajustes manuales de stock

**Objetivo de la etapa:** implementar `POST /api/inventory/adjust` reutilizando el mismo patrón transaccional de la Etapa 3, pero más simple (solo 2 tablas afectadas), más el historial de movimientos por producto.

**Requisito previo:** Etapa 3 completada y verificada (el modelo `InventoryMovement` ya existe desde ahí).

---

## Paso 1 — Por qué esto es más simple que la Etapa 3

En la Etapa 3 la transacción tenía que iterar sobre N productos de un carrito y bloquear cada fila. Aquí es **un solo producto por request**, así que la transacción es más corta:

1. Leer el stock actual del producto (con bloqueo de fila, igual que en ventas).
2. Calcular el delta (`nuevo_stock - stock_actual`).
3. Actualizar `products.stock`.
4. Insertar un registro en `inventory_movements` con `movement_type: "adjustment"`.

No hay validación de "stock suficiente" aquí (a diferencia de ventas) porque un ajuste puede subir o bajar el stock libremente — es corrección manual, no una venta.

---

## Paso 2 — Schema Pydantic

```python
# app/schemas/inventory.py
from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime

class StockAdjustment(BaseModel):
    product_id: UUID
    new_stock: float = Field(ge=0, description="Nuevo valor absoluto de stock, no un delta")
    notes: Optional[str] = None

class InventoryMovementOut(BaseModel):
    id: UUID
    product_id: UUID
    movement_type: str
    quantity_change: float
    reference_id: Optional[UUID]
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
```

`new_stock` se valida con `ge=0` porque no tiene sentido un stock negativo tras un ajuste — si el negocio necesita registrar una merma, se hace bajando `new_stock` al valor correcto, no con números negativos.

---

## Paso 3 — El endpoint transaccional

```python
# app/routers/inventory.py
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
```

**Puntos clave:**

- **`with_for_update()`** otra vez, por la misma razón que en Etapa 3: si alguien está vendiendo ese producto justo cuando tú haces un ajuste manual desde otra pantalla, uno de los dos espera al otro en vez de pisarse.
- El caso `change == 0` evita insertar movimientos "fantasma" cuando el usuario confirma un ajuste sin cambiar realmente el número — mantiene el historial limpio para auditar de verdad.
- `reference_id` queda en `None` para ajustes manuales — solo se usa en ventas (`reference_id = sale_id`), como ya viste en la Etapa 3.
- `GET /movements` está limitado a 50 resultados y ordenado por fecha descendente, igual que espera el frontend hoy.

---

## Paso 4 — Registrar el producto y el movimiento inicial al crear productos con stock > 0

Este pendiente quedó señalado desde la Etapa 2: cuando se crea un producto con `stock > 0`, hay que generar también un `inventory_movement` de tipo `"initial"`. Ahora que existe el modelo `InventoryMovement`, se completa ese punto suelto:

```python
# app/routers/products.py — modificar el create_product de la Etapa 2
from app.models.inventory_movement import InventoryMovement

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
```

Esto cierra el pendiente de la Etapa 2 sin necesidad de volver a tocar esa etapa por separado.

---

## Paso 5 — Registrar el router

```python
# app/main.py
from app.routers import inventory
app.include_router(inventory.router)
```

---

## Paso 6 — Casos de prueba obligatorios

1. **Ajuste hacia abajo** (ej. merma detectada en conteo físico) → `quantity_change` debe quedar negativo y `products.stock` debe reflejar el nuevo valor exacto.
2. **Ajuste hacia arriba** (ej. se encontró stock que no estaba contado) → `quantity_change` positivo.
3. **Ajuste con el mismo valor de stock actual** → no debe crear ningún registro en `inventory_movements`.
4. **Ajuste simultáneo con una venta del mismo producto** — igual que el caso de concurrencia de la Etapa 3, confirmar que uno espera al otro y el stock final es consistente (no se pierde ningún cambio).
5. **Crear producto con `stock: 10`** → debe aparecer automáticamente un movimiento `"initial"` con `quantity_change: 10`.
6. **`GET /api/inventory/movements?product_id=X`** → debe devolver máximo 50 registros, más recientes primero.

---

## Checklist de salida de la etapa

- [ ] `POST /api/inventory/adjust` corre en transacción con bloqueo de fila
- [ ] No se crean movimientos cuando el ajuste no cambia el stock
- [ ] `GET /api/inventory/movements` respeta el límite de 50 y el orden descendente
- [ ] El pendiente de la Etapa 2 (movimiento `"initial"` al crear producto con stock) queda resuelto
- [ ] Los 6 casos de prueba del Paso 6 verificados manualmente

Con esto, la pantalla `/inventory` del frontend puede migrar completamente al backend: listar, crear, editar y ahora también ajustar stock con trazabilidad completa. La Etapa 5 aborda CxC y CxP — los abonos de clientes y proveedores.
