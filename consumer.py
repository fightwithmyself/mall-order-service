import pika
import redis
import pymysql
from dotenv import load_dotenv
import os

load_dotenv()

# Redis连接（兼容Redis3.2 RESP2）
r = redis.Redis(
    host=os.getenv("REDIS_HOST"),
    port=int(os.getenv("REDIS_PORT")),
    decode_responses=True
    
)

# MySQL连接
def get_mysql_conn():
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST"),
        port=int(os.getenv("MYSQL_PORT")),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DB"),
        charset="utf8mb4"
    )

mq_params = pika.ConnectionParameters(
    host=os.getenv("RABBITMQ_HOST"),
    port=int(os.getenv("RABBITMQ_PORT")),
    credentials=pika.PlainCredentials(os.getenv("RABBITMQ_USER"), os.getenv("RABBITMQ_PASS"))
)

def callback(ch, method, properties, body):
    data = body.decode()
    print("收到MQ消息：", data)
    order_id, product_id, buy_num, msg_id = data.split(",")

    conn = get_mysql_conn()
    cur = conn.cursor()

    # 幂等判断：查询消息是否已经处理过
    cur.execute("SELECT id FROM msg_record WHERE msg_id=%s", (msg_id,))
    record = cur.fetchone()
    if record:
        print(f"消息 {msg_id} 已处理，跳过，直接ACK")
        cur.close()
        conn.close()
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    # 1.扣减Redis库存
    r.decrby(f"stock:{product_id}", int(buy_num))
    print(f"订单{order_id}，商品{product_id}，扣减库存 {buy_num}")

    # 2.更新订单状态为成功
    cur.execute("UPDATE orders SET status=1 WHERE id=%s", (order_id,))
    # 3.写入幂等记录表，标记该消息已消费
    cur.execute("INSERT INTO msg_record(msg_id) VALUES(%s)", (msg_id,))
    conn.commit()

    cur.close()
    conn.close()
    # 手动ACK，确认消费完成
    ch.basic_ack(delivery_tag=method.delivery_tag)

if __name__ == "__main__":
    conn = pika.BlockingConnection(mq_params)
    channel = conn.channel()
    channel.queue_declare(queue="order_stock_queue", durable=True)
    channel.basic_consume(queue="order_stock_queue", on_message_callback=callback)
    print("✅ 消费者启动成功，等待MQ消息...")
    channel.start_consuming()
