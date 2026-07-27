# Multimarket Backend

API REST construida con **FastAPI** que sirve como backend del Sistema Multimarket. Se conecta a **Supabase** (PostgreSQL + Auth) y valida los JWT emitidos por Supabase Auth para proteger los endpoints.

## Tech Stack

- **FastAPI** — framework web async
- **SQLAlchemy** — ORM para PostgreSQL
- **PyJWT** — validación de tokens JWT de Supabase
- **Docker** — contenedorización
- **Supabase** — base de datos PostgreSQL y autenticación

## Estructura del proyecto

```
multimarket-backend/
├── app/
│   ├── main.py                 # Instancia FastAPI, CORS, routers
│   ├── config.py               # Settings (variables de entorno)
│   ├── db.py                   # Engine SQLAlchemy + sesión
│   ├── auth/
│   │   ├── jwt.py              # Verificación del JWT de Supabase
│   │   └── dependencies.py     # get_current_user() como Depends
│   ├── models/
│   │   └── __init__.py         # Modelos SQLAlchemy
│   └── routers/
│       └── auth.py             # /api/auth/me
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── .dockerignore
```

## Requisitos previos

- Docker y Docker Compose
- Un proyecto en [Supabase](https://supabase.com) con Auth habilitado

## Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/jimenaazocar05/multimarket-backend.git
cd multimarket-backend
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
```

Editar `.env` con tus credenciales:

| Variable | Dónde obtenerla |
|---|---|
| `DATABASE_URL` | Supabase → Project Settings → Database → Connection string |
| `SUPABASE_URL` | Supabase → Project Settings → API → URL |
| `SUPABASE_JWT_SECRET` | Supabase → Project Settings → API → JWT Secret |
| `FRONTEND_ORIGIN` | Dominio donde corre tu frontend |

### 3. Levantar con Docker

```bash
docker compose up --build
```

El servidor estará disponible en `http://localhost:8000`.

## API Endpoints

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| `GET` | `/health` | ❌ | Health check |
| `GET` | `/api/auth/me` | ✅ Bearer | Retorna info del usuario autenticado |

### Ejemplo de uso

```bash
# Health check
curl http://localhost:8000/health

# Obtener usuario autenticado (requiere token de Supabase)
curl http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer <tu-token-jwt>"
```

### Respuestas

**`GET /health`**
```json
{ "status": "ok" }
```

**`GET /api/auth/me`**
```json
{
  "id": "uuid-del-usuario",
  "email": "usuario@ejemplo.com",
  "role": "authenticated"
}
```

## Desarrollo local sin Docker

```bash
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Documentación interactiva

FastAPI genera documentación automática:

- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`
