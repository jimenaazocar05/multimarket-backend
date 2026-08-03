"""Crea todas las tablas del esquema en la base configurada por DATABASE_URL.

Uso:
    python scripts/init_db.py
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.db import Base, engine
import app.models  # noqa: F401 — registra todos los modelos en Base.metadata


def main():
    Base.metadata.create_all(bind=engine)
    tables = sorted(Base.metadata.tables.keys())
    print(f"Tablas creadas ({len(tables)}):")
    for t in tables:
        print(f"  - {t}")


if __name__ == "__main__":
    main()
