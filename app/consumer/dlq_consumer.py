"""死信消费者：处理超时未支付订单

下单时向 order_timeout_queue（无消费者，TTL=ORDER_TIMEOUT_SECONDS）投递一条消息，
到期后消息经 dlx_exchange 进入 dlq_order_timeout，由这里消费：
订单仍是「待支付」则关闭并归还库存；已支付 / 已取消则直接忽略。

启动：python -m app.consumer.dlq_consumer
"""
import json
import logging
import time

from app.core.mq_client import DL_QUEUE, run_consumer
from app.models.order import OrderStatus
from app.services.order_service import close_order

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("dlq_consumer")


def _parse_order_id(body: bytes) -> int:
    data = json.loads(body)
    return int(data["order_id"] if isinstance(data, dict) else data)


def callback(ch, method, properties, body):
    try:
        order_id = _parse_order_id(body)
        closed = close_order(order_id, OrderStatus.CANCEL_TIMEOUT)
        logger.info("[死信] 订单 %s %s", order_id, "超时关闭，库存已归还" if closed else "无需处理（已支付或已关闭）")
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except (ValueError, KeyError, TypeError):
        logger.error("非法消息，丢弃: %r", body)
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception:
        logger.exception("处理超时订单失败")
        if method.redelivered:
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        else:
            time.sleep(1)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)


if __name__ == "__main__":
    run_consumer(DL_QUEUE, callback)
