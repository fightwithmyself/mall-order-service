"""库存消费者：异步扣减 MySQL 库存

Redis 库存已在下单时由 Lua 预扣，这里只负责把扣减落到 MySQL（最终一致），不再动 Redis。
幂等：先插入 msg_record（msg_id 唯一），重复消息会因唯一键冲突被跳过。

启动：python -m app.consumer.stock_consumer
"""
import json
import logging
import time

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.core.mq_client import STOCK_QUEUE, run_consumer
from app.core.mysql_client import SessionLocal
from app.models.order import MsgRecord, Order, OrderStatus
from app.models.product import Product

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("stock_consumer")


def handle_stock_msg(data: dict) -> None:
    order_id, product_id, buy_num, msg_id = (
        int(data["order_id"]), int(data["product_id"]), int(data["buy_num"]), str(data["msg_id"]),
    )

    with SessionLocal() as sess:
        # 1) 幂等：插入消息记录，重复则直接跳过
        try:
            sess.add(MsgRecord(msg_id=msg_id))
            sess.flush()
        except IntegrityError:
            sess.rollback()
            logger.info("消息 %s 已处理，跳过", msg_id)
            return

        # 2) 锁订单行（与支付 / 关单互斥）；订单已关闭则不再扣库存
        order = sess.execute(select(Order).where(Order.id == order_id).with_for_update()).scalar_one_or_none()
        if order is None or order.status not in (OrderStatus.PENDING_PAY.value, OrderStatus.PAID.value):
            logger.info("订单 %s 不存在或已关闭，跳过扣库存", order_id)
            sess.commit()
            return
        if order.stock_deducted:
            sess.commit()
            return

        # 3) 条件扣减，库存不足时不会扣成负数
        res = sess.execute(
            update(Product).where(Product.id == product_id, Product.stock >= buy_num)
            .values(stock=Product.stock - buy_num)
        )
        if res.rowcount == 0:
            logger.warning("MySQL 库存不足 product_id=%s buy_num=%s，请检查 Redis 与 MySQL 库存是否一致", product_id, buy_num)
        else:
            order.stock_deducted = 1
        sess.commit()
        logger.info("订单 %s 扣库存完成 product_id=%s -%s", order_id, product_id, buy_num)


def callback(ch, method, properties, body):
    try:
        data = json.loads(body)
        handle_stock_msg(data)
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except (ValueError, KeyError, TypeError):
        logger.error("非法消息，丢弃: %r", body)
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception:
        logger.exception("处理库存消息失败")
        if method.redelivered:                      # 已重试过一次仍失败，丢弃避免死循环
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        else:
            time.sleep(1)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


if __name__ == "__main__":
    run_consumer(STOCK_QUEUE, callback)
