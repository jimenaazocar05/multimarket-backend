"""Script para crear usuarios desde la línea de comandos.

Uso:
    cd multimarket-backend
    python scripts/create_user.py <nombre> <username> <password> [rol]

Ejemplo:
    python scripts/create_user.py "Natalia" natt natalia123
    python scripts/create_user.py "Jose" jose jose123 admin

El rol es opcional (por defecto "vendedor"; puede ser "admin" o "vendedor").
Si el username ya existe, lo omite sin error.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import SessionLocal, Base, engine
from app.models import *  # noqa: F401, F403
from app.models.user import User
from app.security import hash_password

ROLES = ("admin", "vendedor")


def create_user(name: str, username: str, password: str, role: str = "vendedor") -> None:
    if role not in ROLES:
        print(f"[ERROR] Rol inválido: '{role}'. Debe ser uno de: {', '.join(ROLES)}")
        sys.exit(1)

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
            role=role,
            active=True,
        )
        db.add(user)
        db.commit()
        print(f"[OK] Usuario creado: username={username}  nombre={name}  rol={role}")
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) not in (4, 5):
        print("Uso: python scripts/create_user.py <nombre> <username> <password> [rol]")
        sys.exit(1)

    name, username, password = sys.argv[1], sys.argv[2], sys.argv[3]
    role = sys.argv[4] if len(sys.argv) == 5 else "vendedor"
    create_user(name, username, password, role)
