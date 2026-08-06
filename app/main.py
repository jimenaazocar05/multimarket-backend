from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
from app.config import settings
from app.routers import products, customers, suppliers, sales, inventory, receivables, payables, dashboard, reports
from app.routers import auth, users
from app.db import Base, engine
import app.models  # noqa: F401 — registra todos los modelos (incluido User)

app = FastAPI(title="Multimarket API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    """Crea las tablas que falten (no destructivo)."""
    Base.metadata.create_all(bind=engine)

    # Migración ligera: agrega la columna `role` a `users` si aún no existe
    # (el proyecto no usa Alembic; create_all no altera tablas existentes).
    inspector = inspect(engine)
    if "users" in inspector.get_table_names():
        columns = {c["name"] for c in inspector.get_columns("users")}
        if "role" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR NOT NULL DEFAULT 'vendedor'"))
                # El usuario "admin" existente debe quedar como administrador,
                # de lo contrario nadie podría acceder al nuevo panel de roles.
                conn.execute(text("UPDATE users SET role = 'admin' WHERE lower(username) = 'admin'"))


# --- Routers ---
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(products.router)
app.include_router(customers.router)
app.include_router(suppliers.router)
app.include_router(sales.router)
app.include_router(inventory.router)
app.include_router(receivables.router)
app.include_router(payables.router)
app.include_router(dashboard.router)
app.include_router(reports.router)


# --- Health check ---
@app.get("/health")
def health():
    return {"status": "ok"}
