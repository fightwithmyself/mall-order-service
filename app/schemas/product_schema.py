from pydantic import BaseModel

# 商品响应结构
class ProductResp(BaseModel):
    id: int
    product_name: str
    stock: int
    price: float

    class Config:
        from_attributes = True
