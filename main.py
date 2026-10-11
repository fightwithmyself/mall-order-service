from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import pika
import redis
import pymysql
import uuid
from dotenv import load_dotenv
import os

load_dotenv()
app = FastAPI(title="订单异步扣减库存服务")

# 全局异常捕获
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"code": 500, "msg": f"服务器异常: {str(exc)}"}
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

# Redis连接（兼容Redis3.2，RESP2协议，关闭HELLO命令）
r = redis.Redis(
    host=os.getenv("REDIS_HOST"),
    port=int(os.getenv("REDIS_PORT")),
    decode_responses=True
   
)

# RabbitMQ连接参数
mq_params = pika.ConnectionParameters(
    host=os.getenv("RABBITMQ_HOST"),
    port=int(os.getenv("RABBITMQ_PORT")),
    credentials=pika.PlainCredentials(os.getenv("RABBITMQ_USER"), os.getenv("RABBITMQ_PASS"))
)

# 请求参数校验模型
class OrderCreate(BaseModel):
    product_id: int = Field(gt=0, description="商品ID必须大于0")
    buy_num: int = Field(gt=0, description="购买数量必须大于0")

@app.post("/order/create")
def create_order(req: OrderCreate):
    product_id = req.product_id
    buy_num = req.buy_num

    # Lua脚本：原子判断库存+扣库存，防止并发超卖
    lua_script = """
    local stock = redis.call('get',KEYS[1])
    if tonumber(stock) >= tonumber(ARGV[1]) then
        redis.call('decrby',KEYS[1],ARGV[1])
        return 1
    else
        return 0
    end
    """
    key = f"stock:{product_id}"
    res = r.eval(lua_script, 1, key, buy_num)
    if res == 0:
        return {"code": -1, "msg": "库存不足"}

    # 写入MySQL订单记录，状态0：待更新
    conn = get_mysql_conn()
    cur = conn.cursor()
    sql = "INSERT INTO orders(product_id, buy_num, status) VALUES(%s,%s,0)"
    cur.execute(sql, (product_id, buy_num))
    conn.commit()
    order_id = cur.lastrowid
    cur.close()
    conn.close()

    # 生成全局唯一消息ID，用于幂等
    msg_id = str(uuid.uuid4())
    msg = f"{order_id},{product_id},{buy_num},{msg_id}"

    # 发送消息到RabbitMQ，消息持久化
    conn_mq = pika.BlockingConnection(mq_params)
    ch = conn_mq.channel()
    ch.queue_declare(queue="order_stock_queue", durable=True)
    ch.basic_publish(
        exchange="",
        routing_key="order_stock_queue",
        body=msg,
        properties=pika.BasicProperties(
            delivery_mode=2,  # 消息持久化
            message_id=msg_id
        )
    )
    conn_mq.close()

    return {"code": 0, "msg": "下单成功", "order_id": order_id}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
