from pydantic import BaseModel, Field
from typing import Optional

class ProductBase(BaseModel):
    sku: int
    name: str
    price: float
    discount: float
    category: str
    current_stock: int
    department_id: str
    monthly_volume: Optional[float] = 0.0
    cluster: Optional[str] = "LOW PERFORMERS"

class ProductCreate(ProductBase):
    pass

class ProductOut(ProductBase):
    id: int = Field(..., description="Integer SKU ID matching frontend expectations")
    id_str: str = Field(..., description="String MongoDB ObjectID representation")

    class Config:
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "sku": 1360,
                "name": "Smart watch ",
                "price": 327.75,
                "discount": 0.04,
                "category": "Sporting Goods",
                "current_stock": 480,
                "department_id": "2",
                "monthly_volume": 70.5,
                "cluster": "VOLUME DRIVERS",
                "id": 1360,
                "id_str": "6a3e6bfa2ea9d39d097fe5a4"
            }
        }
