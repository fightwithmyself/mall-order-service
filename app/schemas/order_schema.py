from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class OrderCreateReq(BaseModel):
    user_id: int = Field(gt=0, description="用户ID")
    product_id: int = Field(gt=0, description="商品ID")
    buy_num: int = Field(gt=0, le=99, description="购买数量")


class OrderResp(BaseModel):
    id: int
    order_no: str
    user_id: int
    product_id: int
    product_name: Optional[str] = None
    buy_num: int
    total_price: float
    status: int
    status_text: str
    create_time: datetime
    pay_time: Optional[datetime] = None
    remaining_seconds: int = 0   # 待支付订单距离自动关闭的剩余秒数
