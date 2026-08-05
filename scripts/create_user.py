"""Script para crear usuarios desde la línea de comandos.

Uso:
    cd multimarket-backend
    python scripts/create_user.py <nombre> <username> <password>

Ejemplo:
    python scripts/create_user.py "Natalia" natt natalia123
    python scripts/create_user.py "Jose" jose jose123

Si el username ya existe, lo omite sin error.
"""
import sys
import os
import hashlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import SessionLocal, Base, engine
from app.models import *  # noqa: F401, F403
from app.models.user import User


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def create_user(name: str, username: str, password: str) -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            print(f"[SKIP] El usuario '{username}' ya existe.")
            return

        user = User(
            name=name,
            username=username,
            password_hash=hash_password(password),
            active=True,
        )
        db.add(user)
        db.commit()
        print(f"[OK] Usuario creado: username={username}  nombre={name}")
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Uso: python scripts/create_user.py <nombre> <username> <password>")
        sys.exit(1)

    _, name, username, password = sys.argv
    create_user(name, username, password)
