from sqlalchemy import Column, Integer, String, DECIMAL
from app.core.mysql_client import Base

class Order(Base):
    __tablename__ = "order_info"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="订单主键")
    order_no = Column(String(64), unique=True, nullable=False, comment="订单编号")
    user_id = Column(Integer, nullable=False, comment="下单用户ID")  # ✅新增用户ID
    product_id = Column(Integer, nullable=False, comment="商品ID")
    buy_num = Column(Integer, nullable=False, comment="购买数量")
    total_price = Column(DECIMAL(10,2), nullable=False, comment="订单总金额")
    status = Column(String(20), nullable=False, default="pending", comment="订单状态 pending待支付 / paid已支付 / cancel取消")
