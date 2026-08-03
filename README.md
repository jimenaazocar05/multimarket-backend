# Multimarket Backend

API REST construida con **FastAPI** que sirve como backend del Sistema Multimarket. Se conecta a un **PostgreSQL** propio (local, vía Docker Compose). No tiene autenticación por ahora — pensado para correr en red local/privada.

**Setup:** solo la base de datos corre en Docker; la API se corre directo con Python (`uvicorn`). No hay contenedor para la API.

## Tech Stack

- **FastAPI** — framework web async
- **SQLAlchemy** — ORM para PostgreSQL
- **PostgreSQL** — base de datos (contenedor local vía Docker Compose)

## Estructura del proyecto

```
multimarket-backend/
├── app/
│   ├── main.py                 # Instancia FastAPI, CORS, routers
│   ├── config.py               # Settings (variables de entorno)
│   ├── db.py                   # Engine SQLAlchemy + sesión
│   ├── models/                 # Modelos SQLAlchemy
│   ├── schemas/                # Schemas Pydantic (request/response)
│   └── routers/                # Endpoints por recurso
├── scripts/
│   ├── init_db.py              # Crea las tablas (Base.metadata.create_all)
│   └── seed.py                 # Puebla la base con datos sintéticos
├── docker-compose.yml          # servicio: db (postgres)
├── requirements.txt
├── .env.example
└── .gitignore
```

## Requisitos previos

- Docker y Docker Compose (solo para la base de datos)
- Python 3.11+

## Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/jimenaazocar05/multimarket-backend.git
cd multimarket-backend
```

### 2. Levantar la base de datos

```bash
docker compose up -d db
```

Levanta Postgres expuesto en el host en el puerto `5434` (para no chocar con otro Postgres local que ya use el `5432`/`5433`). Ajusta el puerto en `docker-compose.yml` si en tu máquina está libre otro.

### 3. Configurar variables de entorno

```bash
cp .env.example .env
```

| Variable | Descripción |
|---|---|
| `DATABASE_URL` | Connection string de Postgres. Como la API corre fuera de Docker, el host es `localhost` y el puerto es el expuesto por `docker-compose.yml` (`5434` por defecto): `postgresql://multimarket:multimarket@localhost:5434/multimarket`. |
| `FRONTEND_ORIGIN` | Dominio donde corre tu frontend (para CORS). Por defecto `http://localhost:8080` (puerto real de Vite en `multimarket-frontend`, no el 5173 típico). |

### 4. Entorno virtual e instalación de dependencias

```bash
python -m venv venv
venv\Scripts\activate         # Windows (usa "source venv/bin/activate" en Linux/Mac)
pip install -r requirements.txt
```

`venv/` está en `.gitignore` — no se sube al repositorio.

### 5. Crear las tablas y (opcional) sembrar datos de prueba

```bash
python scripts/init_db.py
python scripts/seed.py --reset
```

`seed.py` genera datos sintéticos (productos, clientes, proveedores, ventas y cuentas por pagar) con vocabulario real del negocio. `--reset` vacía las tablas antes de sembrar; sin esa bandera, agrega datos sobre lo que ya exista.

### 6. Levantar la API

```bash
uvicorn app.main:app --reload --port 8000
```

### 7. Verificar que quedó arriba

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

## API Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET`/`POST`/`PUT` | `/api/products` | Catálogo de productos |
| `GET`/`POST`/`PUT` | `/api/customers` | Clientes |
| `GET`/`POST`/`PUT` | `/api/suppliers` | Proveedores |
| `GET`/`POST` | `/api/sales` | Ventas |
| `POST` | `/api/inventory/adjust`, `GET /api/inventory/movements` | Inventario |
| `GET`/`POST` | `/api/receivables` | Cuentas por cobrar |
| `GET`/`POST` | `/api/payables` | Cuentas por pagar |
| `GET` | `/api/dashboard` | Resumen del negocio |
| `GET` | `/api/reports` | Reportes por rango de fechas |

Ningún endpoint requiere autenticación actualmente.

## Documentación interactiva

FastAPI genera documentación automática:

- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`
