# Plan de implementación — Etapa 7: Migración a PostgreSQL local (sin Supabase)

**Objetivo de la etapa:** sacar al backend de su dependencia total de Supabase — hoy `DATABASE_URL` apuntaba al Postgres hosteado de Supabase y cada endpoint validaba un JWT de Supabase Auth — y dejarlo corriendo sobre un **PostgreSQL propio, local (Docker)**, sin sistema de autenticación por ahora (uso asumido en red local/privada).

**Requisito previo:** Etapas 1-6 completadas (routers, modelos y schemas de todo el dominio ya existían y funcionaban contra Supabase).

**Decisión de diseño:** al revisar el proyecto se detectó que el backend "FastAPI propio" en realidad delegaba base de datos y autenticación por completo a Supabase. Se decidió: (1) Postgres nuevo **local vía Docker**, no otro proveedor administrado; (2) **sin autenticación propia** — se elimina la verificación de JWT en vez de reemplazarla por un sistema de login propio, para no meter alcance no pedido.

---

## Paso 1 — Postgres local en `docker-compose.yml` ✅ Hecho

Se agregó un servicio `db` (`postgres:16-alpine`) con volumen nombrado para persistencia, y `api` pasa a depender de él:

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: multimarket
      POSTGRES_PASSWORD: multimarket
      POSTGRES_DB: multimarket
    ports:
      - "5432:5432"
    volumes:
      - db_data:/var/lib/postgresql/data
    restart: unless-stopped

  api:
    build: .
    ports: ["8000:8000"]
    env_file: .env
    depends_on: [db]
    restart: unless-stopped

volumes:
  db_data:
```

`Dockerfile` ahora también copia `scripts/` a la imagen (antes solo copiaba `app/`), porque `init_db.py` y `seed.py` viven ahí y se corren con `docker compose exec api ...`.

---

## Paso 2 — Variables de entorno ✅ Hecho

`app/config.py` — se quitaron los campos `SUPABASE_URL` y `SUPABASE_JWT_SECRET` de `Settings` (ya no son variables requeridas, antes tumbaban el arranque si faltaban).

`.env.example` — el `DATABASE_URL` de ejemplo ahora apunta al contenedor `db` (`postgresql://multimarket:multimarket@db:5432/multimarket`); si se corre el backend fuera de Docker, el host cambia a `localhost`.

---

## Paso 3 — Eliminar la verificación de Supabase Auth ✅ Hecho

Sin sistema de auth propio que la reemplace (decisión explícita, ver arriba):

- Borrado `app/auth/` completo (`jwt.py`, `dependencies.py`).
- Borrado `app/routers/auth.py` (el único endpoint que tenía, `/api/auth/me`, no tiene sentido sin Supabase Auth) y su registro en `app/main.py`.
- En los 9 routers de negocio (`products`, `customers`, `suppliers`, `sales`, `inventory`, `receivables`, `payables`, `dashboard`, `reports`) se quitó de cada endpoint el parámetro `user: dict = Depends(get_current_user)` y el import correspondiente.
- `requirements.txt`: fuera `pyjwt`.

Resultado: **ningún endpoint pide `Authorization: Bearer`** — la API queda abierta, pensada para correr detrás de la red local del negocio.

---

## Paso 4 — Crear el esquema sin RLS ✅ Hecho

El esquema vivía como SQL de Supabase en `multimarket-frontend/supabase/migrations/` (con `ENABLE ROW LEVEL SECURITY`, políticas y `GRANT`s específicos de Supabase que ya no aplican sin Supabase Auth). Como los modelos SQLAlchemy en `app/models/` ya definen el esquema completo y coinciden campo a campo, se agregó `scripts/init_db.py`:

```python
from app.db import Base, engine
import app.models  # registra los 8 modelos en Base.metadata

Base.metadata.create_all(bind=engine)
```

Crea las 8 tablas (`products, customers, suppliers, sales, sale_items, payables, payments, inventory_movements`) con sus FKs e índices, sin RLS ni políticas.

---

## Paso 5 — Seeder de datos sintéticos ✅ Hecho

`scripts/seed.py`, standalone, usa `SessionLocal`/modelos de `app/db.py` y `app/models/`. `Faker` agregado a `requirements.txt`.

**Vocabulario real, valores sintéticos**: nombres de productos/clientes/proveedores se tomaron de "Control de Ventas Multimarket 2026.xlsx" (307 productos y 261 clientes únicos en 1269 filas reales) y "Control de Multimarket 2026.xlsx" (hojas CXC/CXP) — son datos propios del negocio del usuario. Los valores (precios, cantidades, fechas, montos, estados) se generan aleatoriamente dentro de los rangos observados; no es una copia literal de las hojas de cálculo.

Orden de inserción (respeta FKs): `products` → `customers` → `suppliers` → `sales`+`sale_items`+`inventory_movements` (con control de stock restante para no vender más de lo disponible) → `payables`(+`payments` para las parcialmente pagadas). Proporciones calibradas contra el Excel real: ~76% ventas pagadas / 24% a crédito, ~55% cuentas por pagar pendientes / 45% saldadas.

Flag `--reset` (default apagado) vacía las tablas de negocio en orden de dependencia antes de sembrar. Semilla fija (`SEED = 42`) para reproducibilidad. Imprime un resumen de filas insertadas por tabla.

---

## Paso 6 — Casos de prueba obligatorios ⏳ Pendiente de ejecutar

Nada de esto se ha corrido todavía — falta crear `multimarket-backend/.env` (copiado de `.env.example`) para poder levantar el stack:

1. `docker compose up --build` levanta `db` + `api` sin errores.
2. `python scripts/init_db.py` crea las 8 tablas sin errores contra el Postgres del contenedor.
3. `python scripts/seed.py --reset` puebla las tablas y el resumen impreso coincide con los conteos esperados (~110 productos, ~110 clientes, ~18 proveedores, hasta 400 ventas, ~22 cuentas por pagar).
4. `GET http://localhost:8000/health` responde `{"status": "ok"}`.
5. `GET http://localhost:8000/docs` — confirmar que **ningún** endpoint pide autorización.
6. `GET /api/dashboard` y `GET /api/products` devuelven datos sembrados coherentes (stock nunca negativo, `low_stock` no vacío si hay productos por debajo del umbral).
7. Reinicio del contenedor `db` → los datos sembrados persisten (gracias al volumen `db_data`).

---

## Checklist de salida de la etapa

- [x] Servicio `db` (Postgres local) en `docker-compose.yml`, con volumen persistente
- [x] `DATABASE_URL`/`.env.example` apuntando al Postgres local, `SUPABASE_*` eliminados de `config.py`
- [x] Verificación de Supabase Auth eliminada de los 9 routers + `app/auth/` + `app/routers/auth.py` borrados
- [x] `scripts/init_db.py` crea el esquema completo sin RLS
- [x] `scripts/seed.py` genera datos sintéticos con vocabulario real de los Excel y `--reset`
- [x] `README.md` y `Dockerfile` actualizados a la nueva realidad sin Supabase
- [ ] Los 7 casos de prueba del Paso 6 verificados de punta a punta (requiere `.env` real y Docker corriendo)

Con esto el backend deja de depender de Supabase por completo. La Etapa 8 (documentada en `multimarket-frontend/docs/Etapa1_Conexion_Backend_FastAPI.md`) es el corte simétrico del lado del frontend: reemplazar `supabase-js` por llamadas REST a esta API.
