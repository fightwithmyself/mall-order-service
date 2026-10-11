import json
import logging
import threading
import time
from typing import Callable

import pika
from pika.exceptions import AMQPError

from app.core.config import settings

logging.getLogger("pika").setLevel(logging.WARNING)   # pika 默认 INFO 日志过于嘈杂

# ---- 队列 / 交换机名称 ----
STOCK_QUEUE = "order_stock_queue"             # 普通业务队列：异步扣减 MySQL 库存
TIMEOUT_QUEUE = "order_timeout_queue"         # 延迟队列：无消费者，消息 TTL 到期后进入死信交换机
DL_EXCHANGE = "dlx_exchange"                  # 死信交换机
DL_QUEUE = "dlq_order_timeout"                # 死信队列：消费者在这里处理超时未支付订单
DL_ROUTING_KEY = "dlq_order"


def _new_connection() -> pika.BlockingConnection:
    return pika.BlockingConnection(
        pika.ConnectionParameters(
            host=settings.RABBITMQ_HOST,
            port=settings.RABBITMQ_PORT,
            credentials=pika.PlainCredentials(settings.RABBITMQ_USER, settings.RABBITMQ_PASS),
            heartbeat=60,
            blocked_connection_timeout=30,
        )
    )


def declare_topology(channel) -> None:
    """声明全部队列与交换机（幂等；参数必须与 RabbitMQ 上已存在的一致）"""
    channel.queue_declare(queue=STOCK_QUEUE, durable=True)

    channel.exchange_declare(exchange=DL_EXCHANGE, exchange_type="direct", durable=True)
    channel.queue_declare(queue=DL_QUEUE, durable=True)
    channel.queue_bind(queue=DL_QUEUE, exchange=DL_EXCHANGE, routing_key=DL_ROUTING_KEY)

    channel.queue_declare(
        queue=TIMEOUT_QUEUE,
        durable=True,
        arguments={
            "x-message-ttl": settings.ORDER_TIMEOUT_SECONDS * 1000,
            "x-dead-letter-exchange": DL_EXCHANGE,
            "x-dead-letter-routing-key": DL_ROUTING_KEY,
        },
    )


class MQClient:
    """生产者客户端：懒连接 + 发布确认 + 断线自动重连 + 线程锁

    pika 的 BlockingConnection 不是线程安全的，而 FastAPI 的同步接口跑在线程池里，
    因此所有发布操作都用同一把锁串行化。
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._conn = None
        self._channel = None

    def _ensure_channel(self):
        if self._conn is None or self._conn.is_closed or self._channel is None or self._channel.is_closed:
            self._conn = _new_connection()
            self._channel = self._conn.channel()
            self._channel.confirm_delivery()   # 开启发布确认，Broker 没落盘会抛异常
            declare_topology(self._channel)
        return self._channel

    def _publish(self, routing_key: str, payload: dict, message_id: str | None = None) -> None:
        body = json.dumps(payload, ensure_ascii=False)
        props = pika.BasicProperties(delivery_mode=2, message_id=message_id, content_type="application/json")
        with self._lock:
            for attempt in (1, 2):
                try:
                    channel = self._ensure_channel()
                    channel.basic_publish(
                        exchange="", routing_key=routing_key, body=body, properties=props, mandatory=True
                    )
                    return
                except (AMQPError, OSError):
                    # 连接可能因空闲被断开：丢弃旧连接，重连后重试一次
                    self._close_quietly()
                    if attempt == 2:
                        raise

    def _close_quietly(self):
        try:
            if self._conn is not None and self._conn.is_open:
                self._conn.close()
        except Exception:
            pass
        self._conn = None
        self._channel = None

    def publish_stock_msg(self, order_id: int, product_id: int, buy_num: int, msg_id: str) -> None:
        """投递"异步扣库存"消息"""
        self._publish(
            STOCK_QUEUE,
            {"order_id": order_id, "product_id": product_id, "buy_num": buy_num, "msg_id": msg_id},
            message_id=msg_id,
        )

    def publish_timeout_msg(self, order_id: int) -> None:
        """投递延迟消息：TTL 到期后经死信交换机进入死信队列，触发超时关单"""
        self._publish(TIMEOUT_QUEUE, {"order_id": order_id})

    def close(self):
        with self._lock:
            self._close_quietly()


def run_consumer(queue: str, callback: Callable, prefetch: int = 1) -> None:
    """启动消费者（阻塞）。连接断开后自动重连，Ctrl+C 退出。"""
    while True:
        conn = None
        try:
            conn = _new_connection()
            channel = conn.channel()
            declare_topology(channel)
            channel.basic_qos(prefetch_count=prefetch)
            channel.basic_consume(queue=queue, on_message_callback=callback)
            print(f"[OK] 消费者已启动，监听队列：{queue}")
            channel.start_consuming()
        except KeyboardInterrupt:
            print("消费者退出")
            if conn is not None and conn.is_open:
                conn.close()
            return
        except (AMQPError, OSError) as e:
            print(f"[警告] RabbitMQ 连接异常：{e!r}，3 秒后重连")
            time.sleep(3)
