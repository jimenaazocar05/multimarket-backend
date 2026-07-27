# Plan de implementación — Etapa 6: Dashboard y Reportes

**Objetivo de la etapa:** exponer `GET /api/dashboard` y `GET /api/reports`, moviendo al backend los cálculos agregados que hoy hace el frontend después de traer todas las ventas del mes al navegador. Sin transacciones ni riesgo de concurrencia — son solo consultas de agregación en SQL.

**Requisito previo:** Etapas 3 (`Sale`, `SaleItem`) y 4 (`Product`) completadas.

---

## Paso 1 — Por qué esto se calcula en SQL y no en Python

Hoy el frontend trae **todas** las ventas y `sale_items` del mes y suma en el navegador. Eso funciona con pocos datos, pero escala mal (más productos, más ventas, más tiempo de carga) y duplica lógica entre `index.tsx` y `reports.tsx`. Aquí cada cálculo se hace con `func.sum`, `func.count` y `GROUP BY` directamente en la base de datos — la respuesta ya viene lista, sin que el backend tenga que traer miles de filas a memoria para sumarlas él mismo.

---

## Paso 2 — Schemas Pydantic

```python
# app/schemas/dashboard.py
from pydantic import BaseModel
from typing import Optional
from uuid import UUID

class TopProduct(BaseModel):
    product_id: Optional[UUID]
    product_name: str
    revenue: float
    profit: float
    quantity: float

class LowStockProduct(BaseModel):
    id: UUID
    name: str
    stock: float
    low_stock_threshold: float

class DashboardOut(BaseModel):
    day_total: float
    week_total: float
    month_total: float
    month_profit: float
    top_products: list[TopProduct]
    low_stock: list[LowStockProduct]
    open_receivables: float
    customer_count: int

class ReportsOut(BaseModel):
    total_sales: float
    total_cost: float
    total_profit: float
    top_by_revenue: list[TopProduct]
    top_by_profit: list[TopProduct]
```

---

## Paso 3 — Router de Dashboard

```python
# app/routers/dashboard.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, timedelta
from app.db import get_db
from app.auth.dependencies import get_current_user
from app.models.sale import Sale
from app.models.sale_item import SaleItem
from app.models.product import Product
from app.models.customer import Customer
from app.schemas.dashboard import DashboardOut, TopProduct, LowStockProduct

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

@router.get("", response_model=DashboardOut)
def get_dashboard(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    def sum_total(since):
        return float(
            db.query(func.coalesce(func.sum(Sale.total), 0))
            .filter(Sale.sale_date >= since)
            .scalar()
        )

    day_total = sum_total(today)
    week_total = sum_total(week_start)
    month_total = sum_total(month_start)

    month_profit = float(
        db.query(func.coalesce(func.sum(Sale.total - Sale.cost_total), 0))
        .filter(Sale.sale_date >= month_start)
        .scalar()
    )

    top_rows = (
        db.query(
            SaleItem.product_id,
            SaleItem.product_name,
            func.sum(SaleItem.subtotal).label("revenue"),
            func.sum(SaleItem.subtotal - (SaleItem.unit_cost * SaleItem.quantity)).label("profit"),
            func.sum(SaleItem.quantity).label("quantity"),
        )
        .join(Sale, Sale.id == SaleItem.sale_id)
        .filter(Sale.sale_date >= month_start)
        .group_by(SaleItem.product_id, SaleItem.product_name)
        .order_by(func.sum(SaleItem.subtotal).desc())
        .limit(10)
        .all()
    )
    top_products = [
        TopProduct(
            product_id=r.product_id, product_name=r.product_name,
            revenue=float(r.revenue), profit=float(r.profit), quantity=float(r.quantity),
        )
        for r in top_rows
    ]

    low_stock_rows = (
        db.query(Product)
        .filter(Product.active.is_(True))
        .filter(Product.stock <= Product.low_stock_threshold)
        .order_by(Product.stock.asc())
        .all()
    )
    low_stock = [
        LowStockProduct(id=p.id, name=p.name, stock=float(p.stock), low_stock_threshold=float(p.low_stock_threshold))
        for p in low_stock_rows
    ]

    open_receivables = float(
        db.query(func.coalesce(func.sum(Sale.total - Sale.amount_paid), 0))
        .filter(Sale.status == "credit")
        .scalar()
    )

    customer_count = db.query(func.count(Customer.id)).scalar()

    return DashboardOut(
        day_total=day_total,
        week_total=week_total,
        month_total=month_total,
        month_profit=month_profit,
        top_products=top_products,
        low_stock=low_stock,
        open_receivables=open_receivables,
        customer_count=customer_count,
    )
```

**Puntos clave:**

- `week_start` se calcula con `today.weekday()` para que la semana empiece en lunes — si el negocio considera que la semana empieza domingo, este es el único número a ajustar.
- El ranking de top productos usa `SaleItem` (no `Sale`) porque el ingreso y la ganancia son por producto, no por venta completa — cada línea del carrito aporta su propio `subtotal` y costo.
- `low_stock` compara `Product.stock <= Product.low_stock_threshold` directamente en SQL — coincide con la definición que ya usa el frontend hoy.

---

## Paso 4 — Router de Reportes

```python
# app/routers/reports.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date
from app.db import get_db
from app.auth.dependencies import get_current_user
from app.models.sale import Sale
from app.models.sale_item import SaleItem
from app.schemas.dashboard import TopProduct
from app.schemas.dashboard import ReportsOut

router = APIRouter(prefix="/api/reports", tags=["reports"])

@router.get("", response_model=ReportsOut)
def get_reports(
    from_: date = Query(..., alias="from"),
    to: date = Query(...),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    totals = (
        db.query(
            func.coalesce(func.sum(Sale.total), 0).label("total_sales"),
            func.coalesce(func.sum(Sale.cost_total), 0).label("total_cost"),
        )
        .filter(Sale.sale_date >= from_, Sale.sale_date <= to)
        .first()
    )
    total_sales = float(totals.total_sales)
    total_cost = float(totals.total_cost)

    base_query = (
        db.query(
            SaleItem.product_id,
            SaleItem.product_name,
            func.sum(SaleItem.subtotal).label("revenue"),
            func.sum(SaleItem.subtotal - (SaleItem.unit_cost * SaleItem.quantity)).label("profit"),
            func.sum(SaleItem.quantity).label("quantity"),
        )
        .join(Sale, Sale.id == SaleItem.sale_id)
        .filter(Sale.sale_date >= from_, Sale.sale_date <= to)
        .group_by(SaleItem.product_id, SaleItem.product_name)
    )

    top_by_revenue = [
        TopProduct(product_id=r.product_id, product_name=r.product_name,
                   revenue=float(r.revenue), profit=float(r.profit), quantity=float(r.quantity))
        for r in base_query.order_by(func.sum(SaleItem.subtotal).desc()).limit(15).all()
    ]
    top_by_profit = [
        TopProduct(product_id=r.product_id, product_name=r.product_name,
                   revenue=float(r.revenue), profit=float(r.profit), quantity=float(r.quantity))
        for r in base_query.order_by(
            (func.sum(SaleItem.subtotal - (SaleItem.unit_cost * SaleItem.quantity))).desc()
        ).limit(15).all()
    ]

    return ReportsOut(
        total_sales=total_sales,
        total_cost=total_cost,
        total_profit=total_sales - total_cost,
        top_by_revenue=top_by_revenue,
        top_by_profit=top_by_profit,
    )
```

**Nota:** `base_query` se ejecuta dos veces (una por cada `order_by` distinto) en vez de traer todo una sola vez y reordenar en Python — con 15 resultados por ranking esto es intrascendente en costo, y mantiene toda la lógica de agregación dentro de SQL en vez de mezclarla con Python.

La exportación a Excel/PDF **se queda en el frontend**, tal como ya lo tienes con `export.ts` (usa `xlsx` y `jsPDF` en el navegador) — el backend solo entrega los datos ya calculados.

---

## Paso 5 — Registrar los routers

```python
# app/main.py
from app.routers import dashboard, reports
app.include_router(dashboard.router)
app.include_router(reports.router)
```

---

## Paso 6 — Casos de prueba obligatorios

1. **`GET /api/dashboard`** en un día con ventas conocidas → comparar `day_total`, `week_total` y `month_total` contra una suma manual en Supabase Studio.
2. **`month_profit`** → confirmar que coincide con `Σ(total - cost_total)` de las ventas del mes, no con la suma ingenua de precios.
3. **`top_products`** → verificar que el orden es por ingreso (`revenue`) descendente, y que `profit` de cada producto es coherente con su costo unitario real.
4. **`low_stock`** → crear un producto de prueba con `stock` justo en el umbral y confirmar que aparece en la lista.
5. **`open_receivables`** → debe coincidir con la suma de `balance` que devuelve `GET /api/receivables` de la Etapa 5.
6. **`GET /api/reports?from=X&to=Y`** con un rango que cruce un mes completo → comparar `total_sales`/`total_profit` contra el dashboard del mismo período.
7. **Rango de fechas sin ventas** → debe devolver ceros y listas vacías, no un error.

---

## Checklist de salida de la etapa

- [ ] `GET /api/dashboard` con todos los cálculos hechos en SQL (no trayendo todo a Python para sumar)
- [ ] `top_products` calculado sobre `sale_items`, no sobre `sales`
- [ ] `low_stock` usando la comparación `stock <= low_stock_threshold` ya definida
- [ ] `GET /api/reports` con rango de fechas y rankings top 15 por ingreso y por ganancia
- [ ] La exportación a Excel/PDF sigue viviendo en el frontend, sin duplicarse en el backend
- [ ] Los 7 casos de prueba del Paso 6 verificados manualmente

Con esto quedan resueltos los 25 endpoints identificados en el análisis original del frontend. La Etapa 7 es el corte real: migrar cada página del cliente Supabase directo a este backend, y endurecer las políticas RLS para que solo el backend pueda escribir en las tablas.
