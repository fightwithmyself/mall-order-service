from pydantic import BaseModel
from typing import Optional

# 创建订单请求入参
class OrderCreateReq(BaseModel):
    user_id: int        # ✅新增
    product_id: int
    buy_num: int

# 订单返回结构
class OrderResp(BaseModel):
    id: int
    order_no: str
    user_id: int
    product_id: int
    buy_num: int
    total_price: float
    status: str

    class Config:
        from_attributes = True
