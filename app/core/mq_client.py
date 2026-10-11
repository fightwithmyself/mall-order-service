import pika
from app.core.config import settings

def get_mq_channel():
    credentials = pika.PlainCredentials(settings.RABBITMQ_USER, settings.RABBITMQ_PASS)
    params = pika.ConnectionParameters(
        host=settings.RABBITMQ_HOST,
        port=settings.RABBITMQ_PORT,
        credentials=credentials
    )
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    # 声明订单队列，持久化队列
    channel.queue_declare(queue="order_queue", durable=True)
    return connection, channel

# 发送订单消息
def send_order_message(msg: str):
    conn, ch = get_mq_channel()
    ch.basic_publish(
        exchange="",
        routing_key="order_queue",
        body=msg,
        properties=pika.BasicProperties(delivery_mode=2) #消息持久化
    )
    conn.close()
