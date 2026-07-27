# Plan de implementación — Etapa 2: Catálogos de bajo riesgo

**Objetivo de la etapa:** exponer `products`, `customers` y `suppliers` a través del backend, con sus agregados calculados en el servidor (no en el navegador). Sin lógica transaccional compleja todavía — eso llega en la Etapa 3. Al terminar, las páginas `/inventory`, `/customers` y `/suppliers` del frontend pueden apuntar al backend en vez de a Supabase directo.

**Requisito previo:** Etapa 1 completada y verificada (`/health` y `/api/auth/me` funcionando).

---

## Paso 1 — Estructura nueva de archivos

```
multimarket-backend/
├── app/
│   ├── models/
│   │   ├── __init__.py
│   │   ├── product.py
│   │   ├── customer.py
│   │   ├── supplier.py
│   │   ├── sale.py              # necesario para los agregados de customers
│   │   └── payable.py           # necesario para los agregados de suppliers
│   ├── schemas/
│   │   ├── product.py            # Pydantic: request/response
│   │   ├── customer.py
│   │   └── supplier.py
│   └── routers/
│       ├── products.py
│       ├── customers.py
│       └── suppliers.py
```

Los modelos de `sale.py` y `payable.py` se declaran completos en esta etapa (aunque sus routers llegan después) porque los agregados de clientes y proveedores necesitan hacer join/subquery contra ellos.

---

## Paso 2 — Modelos SQLAlchemy

```python
# app/models/product.py
from sqlalchemy import Column, String, Numeric, Boolean, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.db import Base

class Product(Base):
    __tablename__ = "products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String, nullable=True)
    name = Column(String, nullable=False)
    cost = Column(Numeric(12, 2), nullable=False, default=0)
    price = Column(Numeric(12, 2), nullable=False, default=0)
    stock = Column(Numeric(12, 2), nullable=False, default=0)
    low_stock_threshold = Column(Numeric(12, 2), nullable=False, default=5)
    unit = Column(String, nullable=True, default="unidad")
    active = Column(Boolean, nullable=False, default=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

```python
# app/models/customer.py
from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.db import Base

class Customer(Base):
    __tablename__ = "customers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

```python
# app/models/supplier.py
from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.db import Base

class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

```python
# app/models/sale.py
from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.db import Base

class Sale(Base):
    __tablename__ = "sales"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sale_date = Column(DateTime(timezone=True), server_default=func.now())
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)
    customer_name = Column(String, nullable=True)
    total = Column(Numeric(12, 2), nullable=False, default=0)
    cost_total = Column(Numeric(12, 2), nullable=False, default=0)
    status = Column(String, nullable=False, default="paid")  # 'paid' | 'credit'
    amount_paid = Column(Numeric(12, 2), nullable=False, default=0)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

```python
# app/models/payable.py
from sqlalchemy import Column, String, Numeric, Date, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.db import Base

class Payable(Base):
    __tablename__ = "payables"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    supplier_id = Column(UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True)
    supplier_name = Column(String, nullable=True)
    concept = Column(String, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    amount_paid = Column(Numeric(12, 2), nullable=False, default=0)
    due_date = Column(Date, nullable=True)
    issue_date = Column(Date, server_default=func.current_date())
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

> Todos los nombres de tabla y columna coinciden exactamente con las migraciones SQL actuales de Supabase — no hay que tocar el esquema, solo mapearlo.

---

## Paso 3 — Schemas Pydantic (request/response)

```python
# app/schemas/product.py
from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime

class ProductBase(BaseModel):
    code: Optional[str] = None
    name: str
    cost: float = 0
    price: float = 0
    low_stock_threshold: float = 5
    unit: str = "unidad"
    active: bool = True
    notes: Optional[str] = None

class ProductCreate(ProductBase):
    stock: float = 0  # solo se permite fijar stock en la creación

class ProductUpdate(ProductBase):
    pass  # sin stock — el stock solo cambia vía /api/inventory/adjust (Etapa 4)

class ProductOut(ProductBase):
    id: UUID
    stock: float
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
```

```python
# app/schemas/customer.py
from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime

class CustomerBase(BaseModel):
    name: str
    phone: Optional[str] = None
    notes: Optional[str] = None

class CustomerCreate(CustomerBase):
    pass

class CustomerAgg(BaseModel):
    total: float
    owed: float
    count: int

class CustomerOut(CustomerBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    agg: CustomerAgg

    class Config:
        from_attributes = True
```

```python
# app/schemas/supplier.py
from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime

class SupplierBase(BaseModel):
    name: str
    phone: Optional[str] = None
    notes: Optional[str] = None

class SupplierCreate(SupplierBase):
    pass

class SupplierAgg(BaseModel):
    total: float
    owed: float
    count: int

class SupplierOut(SupplierBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    agg: SupplierAgg

    class Config:
        from_attributes = True
```

---

## Paso 4 — Router de productos

```python
# app/routers/products.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import asc
from uuid import UUID
from app.db import get_db
from app.auth.dependencies import get_current_user
from app.models.product import Product
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
    product = Product(**payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    # Nota: si stock > 0, el movimiento inicial en inventory_movements
    # se implementa en la Etapa 4 junto con el resto de inventario.
    return product

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
```

> El endpoint `PUT` recibe `ProductUpdate` (sin campo `stock`), así que es imposible cambiar el stock por esta vía — queda reservado para el endpoint de ajuste de la Etapa 4.

---

## Paso 5 — Router de clientes (con agregados)

```python
# app/routers/customers.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from uuid import UUID
from app.db import get_db
from app.auth.dependencies import get_current_user
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
def list_customers(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
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
def customer_sales(customer_id: UUID, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return (
        db.query(Sale)
        .filter(Sale.customer_id == customer_id)
        .order_by(Sale.sale_date.desc())
        .all()
    )

@router.post("", status_code=201)
def create_customer(payload: CustomerCreate, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    customer = Customer(**payload.model_dump())
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer

@router.put("/{customer_id}")
def update_customer(customer_id: UUID, payload: CustomerCreate, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(404, "Cliente no encontrado")
    for field, value in payload.model_dump().items():
        setattr(customer, field, value)
    db.commit()
    db.refresh(customer)
    return customer
```

**Nota sobre `owed`:** se calcula sumando `total - amount_paid` únicamente de las ventas con `status = 'credit'` — coincide exactamente con la definición que ya usa el frontend hoy en `data.ts`.

---

## Paso 6 — Router de proveedores (mismo patrón, contra `payables`)

```python
# app/routers/suppliers.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
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
def update_supplier(supplier_id, payload: SupplierCreate, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        raise HTTPException(404, "Proveedor no encontrado")
    for field, value in payload.model_dump().items():
        setattr(supplier, field, value)
    db.commit()
    db.refresh(supplier)
    return supplier
```

**A diferencia de `owed` en clientes**, aquí no se filtra por status porque `payables` no tiene un campo `status` — el saldo pendiente es simplemente `amount - amount_paid` para todas las facturas.

---

## Paso 7 — Registrar los routers en `main.py`

```python
# app/main.py (agregar a lo ya existente de la Etapa 1)
from app.routers import products, customers, suppliers

app.include_router(products.router)
app.include_router(customers.router)
app.include_router(suppliers.router)
```

---

## Paso 8 — Pruebas manuales end-to-end

1. `GET /api/products` → debe devolver la misma lista que hoy ves en `/inventory` del frontend.
2. `POST /api/products` con un producto de prueba → confirmar que aparece en Supabase Studio.
3. `GET /api/customers` → verificar que `agg.total` y `agg.owed` coinciden con lo que el frontend calcula hoy en el navegador (comparar contra un cliente con ventas fiadas conocidas).
4. `GET /api/suppliers` → mismo tipo de verificación contra un proveedor con facturas pendientes.
5. Probar `PUT /api/products/:id` e intentar mandar `stock` en el body → confirmar que el schema `ProductUpdate` lo ignora silenciosamente (no rompe, pero tampoco lo aplica).

---

## Checklist de salida de la etapa

- [ ] `GET/POST/PUT /api/products` funcionando, sin permitir editar `stock`
- [ ] `GET /api/customers` con `agg.total`, `agg.owed`, `agg.count` calculados en SQL (no en Python después de traer todo)
- [ ] `GET /api/customers/:id/sales` funcionando
- [ ] `GET/POST/PUT /api/suppliers` con agregados equivalentes
- [ ] Los tres routers protegidos con `Depends(get_current_user)` de la Etapa 1
- [ ] Verificado contra datos reales que los números coinciden con lo que el frontend muestra hoy

Con esto, las páginas `/inventory`, `/customers` y `/suppliers` ya pueden migrar su fuente de datos del cliente Supabase directo al backend. La Etapa 3 aborda `POST /api/sales`, la operación transaccional más delicada del sistema.
