"""Siembra el inventario real de Multimarket a partir del conteo fisico
(hoja de inventario escrita a mano). Por ahora solo carga productos con su
nombre y stock inicial -- los precios (costo/venta) se completan luego desde
el frontend, asi que quedan en 0.

Uso:
    python scripts/seed.py            # agrega productos sobre lo que ya exista
    python scripts/seed.py --reset    # vacia products/inventory_movements antes de sembrar
"""
import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.db import Base, SessionLocal, engine
from app.models.inventory_movement import InventoryMovement
from app.models.product import Product

# --- Inventario fisico (nombre, cantidad en stock, unidad) ----------------
# Extraido de la hoja de conteo manuscrita. Los precios no vienen en la hoja
# (se cargan despues desde el frontend), asi que cost/price quedan en 0.
INVENTORY = [
    # -- Columna 1 --
    ("Jamon", 397, "gr"),
    ("Queso Duro", 3138, "gr"),
    ("Quesillo", 3, "unidad"),
    ("Coca Cola 2 litros", 18, "unidad"),
    ("Mortadela peq", 1, "unidad"),
    ("Mortadela Grande", 3, "unidad"),
    ("Refresco 1,5 litros", 10, "unidad"),
    ("Leche liquida", 8, "unidad"),
    ("Polet Frambuesa", 2, "unidad"),
    ("Polet Coco Fresa", 2, "unidad"),
    ("Polet Crunch", 1, "unidad"),
    ("Polet Ferrero", 2, "unidad"),
    ("Polet Max", 2, "unidad"),
    ("Wonder", 3, "unidad"),
    ("Mausi", 3, "unidad"),
    ("Chocomant", 4, "unidad"),
    ("Tinita", 1, "unidad"),
    ("Supercono", 6, "unidad"),
    ("Papel Higienico", 2, "unidad"),
    ("Suavizante", 1, "unidad"),
    ("Cloro", 1, "unidad"),
    ("Huevos", 0.5, "carton"),
    ("Vinagre", 1, "unidad"),
    ("Aceite peq", 4, "unidad"),
    ("Aceite grande", 3, "unidad"),
    # -- Columna 2 --
    ("Azucar", 1, "unidad"),
    ("Leche en Polvo", 3, "unidad"),
    ("Crema Pastelera", 1, "unidad"),
    ("Leche evaporada", 1, "unidad"),
    ("Onoto en granitos", 2, "sobre"),
    ("Polvo para hornear", 5, "unidad"),
    ("Sopa Maggi", 1, "unidad"),
    ("Cubitos", 36, "unidad"),
    ("Sazonador de Costilla", 12, "unidad"),
    ("Atun", 2, "unidad"),
    ("Compota", 7, "unidad"),
    ("Maiz en lata", 3, "unidad"),
    ("Crema Chantilly", 1, "unidad"),
    ("Lata de Tomate", 1, "unidad"),
    ("Tristras", 1, "unidad"),
    ("Sardina", 6, "unidad"),
    ("Zagaz", 1, "unidad"),
    ("Toallas Sanitarias", 3, "unidad"),
    ("Pasta p'pastícho", 4, "unidad"),
    ("Mantequilla Grand Marvesa", 1, "unidad"),
    ("Harina Pan", 2, "unidad"),
    ("Harina Mary", 4, "unidad"),
    ("Arroz Mary", 4, "unidad"),
    ("Ketchup G", 3, "unidad"),
    ("Pasta Corta Horizonte", 4, "unidad"),
    ("Pasta Corta Mary", 1, "unidad"),
    # -- Columna 3 --
    ("Pasta Larga", 1, "unidad"),
    ("Harina Leudante Mary", 2, "unidad"),
    ("Harina Todo Uso Mary", 7, "unidad"),
    ("Rapido", 4, "unidad"),
    ("Chesito", 8, "unidad"),
    ("Crakeñas", 1, "paq"),
    ("Piruetas", 4, "unidad"),
    ("Palitos", 3, "unidad"),
    ("Crackit", 13, "unidad"),
    ("Bianchi", 3, "unidad"),
    ("Galleta Soda", 4, "paq"),
    ("Tip Top Coco", 1, "unidad"),
    ("Tip Top Vainilla", 1, "unidad"),
    ("Chicle A Go Go", 19, "unidad"),
    ("Rulas", 7, "unidad"),
    ("Chupeta Pimpon", 53, "unidad"),
    ("BomBomBon", 24, "unidad"),
    ("Ricatto", 15, "unidad"),
    ("Caramelo Tamarindo", 19, "unidad"),
    ("Galletas Chips (3 unid)", 6, "unidad"),
    ("Galletas pasta seca", 9, "unidad"),
    ("Galletas Chips (2 unid)", 5, "unidad"),
]

DEPENDENCY_ORDER = [InventoryMovement, Product]


def reset_db(db):
    for model in DEPENDENCY_ORDER:
        db.query(model).delete()
    db.commit()


def seed_products(db) -> list[Product]:
    products = []
    for name, stock, unit in INVENTORY:
        product = Product(
            name=name,
            cost=0,
            price=0,
            stock=stock,
            low_stock_threshold=5,
            unit=unit,
            active=True,
        )
        db.add(product)
        products.append(product)
    db.flush()

    for product in products:
        if product.stock > 0:
            db.add(InventoryMovement(
                product_id=product.id,
                movement_type="initial",
                quantity_change=product.stock,
                reference_id=None,
                notes="Stock inicial (seed)",
            ))
    db.commit()
    return products


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="Vacia products/inventory_movements antes de sembrar")
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        if args.reset:
            reset_db(db)

        products = seed_products(db)

        print("Inventario sembrado:")
        print(f"  products: {len(products)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
