# Importar todos los modelos para que SQLAlchemy los registre
from app.models.product import Product
from app.models.customer import Customer
from app.models.supplier import Supplier
from app.models.sale import Sale
from app.models.sale_item import SaleItem
from app.models.payable import Payable
from app.models.inventory_movement import InventoryMovement

__all__ = ["Product", "Customer", "Supplier", "Sale", "SaleItem", "Payable", "InventoryMovement"]
