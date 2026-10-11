import enum
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, Numeric, SmallInteger, String

from app.core.mysql_client import Base


class OrderStatus(int, enum.Enum):
    PENDING_PAY = 0      # 待支付（已预占库存，等待用户支付）
    PAID = 1             # 已支付
    CANCEL_TIMEOUT = 2   # 超时未支付，自动关闭
    CANCEL_MANUAL = 3    # 用户手动取消


STATUS_TEXT = {
    OrderStatus.PENDING_PAY.value: "待支付",
    OrderStatus.PAID.value: "已支付",
    OrderStatus.CANCEL_TIMEOUT.value: "超时已关闭",
    OrderStatus.CANCEL_MANUAL.value: "已取消",
}


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_no = Column(String(32), nullable=False, unique=True, comment="订单号")
    user_id = Column(Integer, nullable=False, index=True, comment="用户ID")
    product_id = Column(Integer, nullable=False, comment="商品ID")
    buy_num = Column(Integer, nullable=False, comment="购买数量")
    total_price = Column(Numeric(10, 2), nullable=False, default=0, comment="订单总价")
    status = Column(
        SmallInteger, nullable=False, default=OrderStatus.PENDING_PAY.value,
        comment="0待支付 1已支付 2超时关闭 3手动取消",
    )
    stock_deducted = Column(SmallInteger, nullable=False, default=0, comment="MySQL库存是否已由消费者扣减")
    create_time = Column(DateTime, nullable=False, default=datetime.now)
    pay_time = Column(DateTime, nullable=True)


class MsgRecord(Base):
    """消息幂等表：msg_id 唯一，消费前先插入，重复消费会触发唯一键冲突"""
    __tablename__ = "msg_record"

    id = Column(Integer, primary_key=True, autoincrement=True)
    msg_id = Column(String(128), nullable=False, unique=True, comment="消息唯一ID")
    create_time = Column(DateTime, nullable=False, default=datetime.now)
