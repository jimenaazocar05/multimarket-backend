# Importar todos los modelos para que SQLAlchemy los registre
from app.models.product import Product
from app.models.customer import Customer
from app.models.supplier import Supplier
from app.models.sale import Sale
from app.models.payable import Payable

__all__ = ["Product", "Customer", "Supplier", "Sale", "Payable"]
