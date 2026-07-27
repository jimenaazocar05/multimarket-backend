# Plan de implementación — Etapa 5: Finanzas — Cuentas por cobrar y por pagar

**Objetivo de la etapa:** implementar el registro de abonos de clientes (CxC) y pagos a proveedores (CxP) usando la tabla unificada `payments`, con las mismas garantías transaccionales de las etapas anteriores: no se puede abonar de más ni dejar un saldo inconsistente.

**Requisito previo:** Etapas 3 (modelo `Sale`) y 2 (modelo `Payable`, `Supplier`) completadas y verificadas.

---

## Paso 1 — Por qué CxC y CxP comparten un solo modelo (`payments`)

A diferencia de ventas e inventario, aquí no hay dos tablas separadas para "abono de cliente" y "pago a proveedor" — el esquema ya definido en Supabase usa **una sola tabla `payments`** con un campo `kind` (`'receivable'` | `'payable'`) que decide si el pago referencia una `sale_id` o un `payable_id`. Esto significa que la lógica de "no abonar más del saldo pendiente" se escribe una sola vez y se reutiliza para ambos casos — es el mismo patrón, solo cambia contra qué tabla se actualiza el `amount_paid`.

---

## Paso 2 — Modelo `Payment`

```python
# app/models/payment.py
from sqlalchemy import Column, String, Numeric, Date, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.db import Base

class Payment(Base):
    __tablename__ = "payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind = Column(String, nullable=False)  # 'receivable' | 'payable'
    sale_id = Column(UUID(as_uuid=True), ForeignKey("sales.id", ondelete="CASCADE"), nullable=True)
    payable_id = Column(UUID(as_uuid=True), ForeignKey("payables.id", ondelete="CASCADE"), nullable=True)
    amount = Column(Numeric(12, 2), nullable=False)
    payment_date = Column(Date, server_default=func.current_date())
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

---

## Paso 3 — Schemas Pydantic

```python
# app/schemas/finance.py
from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import date, datetime

class ReceivablePay(BaseModel):
    sale_id: UUID
    amount: float = Field(gt=0)

class PayableCreate(BaseModel):
    supplier_id: Optional[UUID] = None
    supplier_name: Optional[str] = None
    concept: str
    amount: float = Field(gt=0)
    due_date: Optional[date] = None
    notes: Optional[str] = None

class PayablePay(BaseModel):
    payable_id: UUID
    amount: float = Field(gt=0)

class ReceivableOut(BaseModel):
    id: UUID
    sale_date: datetime
    customer_id: Optional[UUID]
    customer_name: Optional[str]
    total: float
    amount_paid: float
    balance: float
    days_old: int

class PayableOut(BaseModel):
    id: UUID
    supplier_id: Optional[UUID]
    supplier_name: Optional[str]
    concept: str
    amount: float
    amount_paid: float
    balance: float
    due_date: Optional[date]
    issue_date: date
    days_old: int
    overdue: bool
```

`balance`, `days_old` y `overdue` no existen como columnas — se calculan en el router al construir la respuesta, tal como los espera el frontend hoy.

---

## Paso 4 — Router de cuentas por cobrar

```python
# app/routers/receivables.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date, datetime
from app.db import get_db
from app.auth.dependencies import get_current_user
from app.models.sale import Sale
from app.models.payment import Payment
from app.schemas.finance import ReceivablePay, ReceivableOut

router = APIRouter(prefix="/api/receivables", tags=["receivables"])

@router.get("", response_model=list[ReceivableOut])
def list_receivables(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    sales = (
        db.query(Sale)
        .filter(Sale.status == "credit")
        .filter(Sale.total > Sale.amount_paid)
        .order_by(Sale.sale_date.asc())
        .all()
    )
    today = date.today()
    return [
        ReceivableOut(
            id=s.id,
            sale_date=s.sale_date,
            customer_id=s.customer_id,
            customer_name=s.customer_name,
            total=float(s.total),
            amount_paid=float(s.amount_paid),
            balance=float(s.total - s.amount_paid),
            days_old=(today - s.sale_date.date()).days,
        )
        for s in sales
    ]

@router.post("/pay", response_model=ReceivableOut)
def pay_receivable(payload: ReceivablePay, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    # Bloqueo de fila — mismo motivo de siempre: dos abonos simultáneos
    # a la misma venta no deben pisarse ni sobrepasar el saldo juntos.
    sale = (
        db.query(Sale)
        .filter(Sale.id == payload.sale_id)
        .with_for_update()
        .first()
    )
    if not sale:
        raise HTTPException(404, "Venta no encontrada")

    balance = float(sale.total - sale.amount_paid)
    if payload.amount > balance:
        raise HTTPException(422, f"El abono ({payload.amount}) excede el saldo pendiente ({balance})")

    try:
        db.add(Payment(kind="receivable", sale_id=sale.id, amount=payload.amount))
        sale.amount_paid = sale.amount_paid + payload.amount
        if sale.amount_paid >= sale.total:
            sale.status = "paid"
        db.commit()
        db.refresh(sale)
    except Exception:
        db.rollback()
        raise

    today = date.today()
    return ReceivableOut(
        id=sale.id, sale_date=sale.sale_date, customer_id=sale.customer_id,
        customer_name=sale.customer_name, total=float(sale.total),
        amount_paid=float(sale.amount_paid), balance=float(sale.total - sale.amount_paid),
        days_old=(today - sale.sale_date.date()).days,
    )
```

---

## Paso 5 — Router de cuentas por pagar

```python
# app/routers/payables.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date
from app.db import get_db
from app.auth.dependencies import get_current_user
from app.models.payable import Payable
from app.models.payment import Payment
from app.schemas.finance import PayableCreate, PayablePay, PayableOut

router = APIRouter(prefix="/api/payables", tags=["payables"])

def _to_out(p: Payable) -> PayableOut:
    today = date.today()
    balance = float(p.amount - p.amount_paid)
    return PayableOut(
        id=p.id, supplier_id=p.supplier_id, supplier_name=p.supplier_name,
        concept=p.concept, amount=float(p.amount), amount_paid=float(p.amount_paid),
        balance=balance, due_date=p.due_date, issue_date=p.issue_date,
        days_old=(today - p.issue_date).days,
        overdue=bool(p.due_date and p.due_date < today and balance > 0),
    )

@router.get("", response_model=list[PayableOut])
def list_payables(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    payables = db.query(Payable).order_by(Payable.issue_date.desc()).all()
    return [_to_out(p) for p in payables]

@router.post("", response_model=PayableOut, status_code=201)
def create_payable(payload: PayableCreate, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    payable = Payable(**payload.model_dump())
    db.add(payable)
    db.commit()
    db.refresh(payable)
    return _to_out(payable)

@router.post("/pay", response_model=PayableOut)
def pay_payable(payload: PayablePay, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
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
        payable.amount_paid = payable.amount_paid + payload.amount
        db.commit()
        db.refresh(payable)
    except Exception:
        db.rollback()
        raise

    return _to_out(payable)
```

**Nota:** a diferencia de `receivables`, `payables` no tiene un campo `status` que cambiar a `'paid'` — el estado "pagado" se deriva siempre de `balance == 0`, tal como ya lo calcula el frontend hoy. Por eso no hay ningún `if payable.amount_paid >= payable.amount: ...` aquí.

---

## Paso 6 — Registrar los routers

```python
# app/main.py
from app.routers import receivables, payables
app.include_router(receivables.router)
app.include_router(payables.router)
```

---

## Paso 7 — Casos de prueba obligatorios

1. **Abono parcial a una venta a crédito** → `sale.amount_paid` sube, `status` sigue en `'credit'`, aparece en `GET /api/receivables` con el `balance` correcto.
2. **Abono que completa el saldo exacto** → `status` cambia automáticamente a `'paid'` y la venta desaparece de `GET /api/receivables`.
3. **Intento de abonar más del saldo pendiente** → debe rechazar con 422 y no crear ningún `Payment`.
4. **Dos abonos simultáneos a la misma venta que sumados exceden el saldo** → solo uno debe tener éxito (probar con requests concurrentes, igual que en la Etapa 3).
5. **Crear cuenta por pagar y pagarla en dos abonos parciales** → verificar `balance` decreciente y que `overdue` se calcula bien contra `due_date`.
6. **Cuenta por pagar vencida sin pagar** (`due_date` en el pasado, `balance > 0`) → `overdue: true` en la respuesta.
7. **`GET /api/receivables`** → confirmar que solo aparecen ventas con `status = 'credit'` y `balance > 0` (una venta ya saldada no debe listarse aunque siga marcada como `'credit'` por algún dato viejo).

---

## Checklist de salida de la etapa

- [ ] `GET /api/receivables` con `balance` y `days_old` calculados en el backend
- [ ] `POST /api/receivables/pay` valida `0 < amount <= balance`, actualiza `amount_paid` y cambia `status` a `'paid'` cuando corresponde
- [ ] `GET/POST /api/payables` funcionando
- [ ] `POST /api/payables/pay` con la misma validación de saldo, sin necesidad de campo `status` (se deriva de `balance`)
- [ ] `overdue` calculado correctamente contra `due_date`
- [ ] Bloqueo de fila (`with_for_update`) en ambos endpoints de pago
- [ ] Los 7 casos de prueba del Paso 7 verificados manualmente

Con esto, `/receivables` y `/payables` en el frontend ya pueden migrar del cliente Supabase directo al backend. La Etapa 6 mueve los cálculos de Dashboard y Reportes al servidor — la parte más liviana de todo el proyecto.
