from typing import Optional

from pydantic import BaseModel


class ProductResp(BaseModel):
    id: int
    product_name: str
    description: Optional[str] = None
    image: Optional[str] = None
    stock: int
    price: float
