"""Script para crear el usuario administrador inicial.

Uso:
    cd multimarket-backend
    python scripts/create_admin.py

Si el usuario ya existe, lo omite.
"""
import sys
import os
import hashlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import SessionLocal, Base, engine
from app.models import *  # noqa: F401, F403 — registra todos los modelos
from app.models.user import User


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def create_admin():
    # Crea la tabla users si no existe todavía
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == "admin").first()
        if existing:
            print("[OK] El usuario 'admin' ya existe - no se sobreescribe.")
            return

        admin = User(
            name="Administrador",
            username="admin",
            password_hash=hash_password("admin123"),
            active=True,
        )
        db.add(admin)
        db.commit()
        print("[OK] Usuario creado:")
        print("    username : admin")
        print("    password : admin123")
        print("\n  [!] Cambia la contrasena en produccion.")
    finally:
        db.close()


if __name__ == "__main__":
    create_admin()
