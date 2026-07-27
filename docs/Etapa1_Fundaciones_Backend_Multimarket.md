# Plan de implementación — Etapa 1: Fundaciones

**Objetivo de la etapa:** tener FastAPI corriendo en Docker, conectado a la misma Postgres de Supabase, validando el JWT que ya emite Supabase Auth, con un endpoint `/health` y `/api/auth/me` funcionando end-to-end desde el frontend.

---

## Paso 1 — Estructura del proyecto

```
multimarket-backend/
├── app/
│   ├── main.py                 # instancia FastAPI, CORS, routers
│   ├── config.py                # settings (env vars)
│   ├── db.py                    # engine SQLAlchemy + sesión
│   ├── auth/
│   │   ├── jwt.py                # validación del JWT de Supabase
│   │   └── dependencies.py       # get_current_user() como Depends
│   ├── models/
│   │   └── __init__.py           # modelos SQLAlchemy (se llenan en etapa 2)
│   └── routers/
│       └── auth.py               # /api/auth/me
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── .dockerignore
```

---

## Paso 2 — Variables de entorno necesarias

```
DATABASE_URL=postgresql://postgres:[password]@[host]:5432/postgres
SUPABASE_URL=https://tyrfeefryxzoohxylkcy.supabase.co
SUPABASE_JWT_SECRET=<lo sacas de Supabase: Project Settings → API → JWT Secret>
FRONTEND_ORIGIN=https://tu-dominio-frontend.com
```

- El `DATABASE_URL` se saca de Supabase en **Project Settings → Database → Connection string** (usa el modo "Session pooler" o "Transaction pooler" según cómo corras el servidor — para un VPS con Docker, "Session pooler" está bien).
- El `SUPABASE_JWT_SECRET` es la clave con la que Supabase firma los tokens. Con esto el backend verifica la firma localmente, sin necesidad de llamar a Supabase en cada request.

---

## Paso 3 — Validación del JWT (la pieza más importante de esta etapa)

Como el frontend ya usa Supabase Auth y manda el token en `Authorization: Bearer <token>`, el backend solo necesita **decodificar y verificar la firma** — no reimplementa login.

```python
# app/auth/jwt.py
import jwt
from fastapi import HTTPException, status
from app.config import settings

def verify_supabase_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido")
```

```python
# app/auth/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.auth.jwt import verify_supabase_token

bearer_scheme = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    payload = verify_supabase_token(credentials.credentials)
    return {
        "id": payload["sub"],
        "email": payload.get("email"),
        "role": payload.get("role", "authenticated"),
    }
```

Este `get_current_user` es lo que se inyecta con `Depends(get_current_user)` en **cada endpoint protegido** de las próximas etapas — queda resuelto de una vez aquí.

---

## Paso 4 — Conexión a la base de datos

```python
# app/db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

`pool_pre_ping=True` es importante porque Supabase puede cerrar conexiones idle — sin esto aparecen errores intermitentes de "conexión cerrada" en producción.

---

## Paso 5 — App principal, CORS y endpoints de prueba

```python
# app/main.py
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.auth.dependencies import get_current_user

app = FastAPI(title="Multimarket API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/api/auth/me")
def me(user: dict = Depends(get_current_user)):
    return user
```

---

## Paso 6 — Docker

```dockerfile
# Dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml
services:
  api:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    restart: unless-stopped
```

Dado que ya existe Caddy corriendo para otros proyectos (ej. `yalatengo.com`), en esta etapa solo se levanta el contenedor local; el reverse proxy con Caddy se conecta en la Etapa 8, cuando esto esté listo para producción.

---

## Paso 7 — `requirements.txt`

```
fastapi
uvicorn[standard]
sqlalchemy
psycopg2-binary
pyjwt
python-dotenv
pydantic-settings
```

---

## Paso 8 — Verificación end-to-end

1. `docker compose up --build` → confirmar que `GET http://localhost:8000/health` responde `{"status":"ok"}`.
2. Desde el frontend (o Postman), tomar el token de la sesión actual de Supabase (`supabase.auth.getSession()` en la consola del navegador) y llamar a `GET http://localhost:8000/api/auth/me` con `Authorization: Bearer <token>`.
3. Confirmar que responde el `id` y `email` correctos del usuario logueado — esto prueba que el backend reconoce la misma sesión que ya usa el frontend, sin tocar nada del login existente.

---

## Checklist de salida de la etapa

- [ ] Contenedor corre y responde `/health`
- [ ] `DATABASE_URL` conecta correctamente a la Postgres de Supabase (probar con un `SELECT 1` rápido)
- [ ] `/api/auth/me` valida el JWT real de una sesión activa del frontend
- [ ] CORS permite llamadas desde el dominio del frontend sin bloqueos
- [ ] `.env.example` documentado para poder replicarlo en el VPS

Con esto queda la base para que en la Etapa 2 solo se agreguen routers y modelos, sin volver a tocar auth, DB ni Docker.
