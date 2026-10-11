```
# 高并发订单异步扣减库存系统
## 项目简介
基于 FastAPI + MySQL + Redis + RabbitMQ 实现的高并发下单系统。
解决电商场景下**并发超卖**和**消息重复消费**问题，采用异步架构削峰填谷，缓解数据库压力。

## 技术栈
- Web框架：FastAPI
- 数据库：MySQL 8.0
- 缓存：Redis 3.2
- 消息队列：RabbitMQ
- 依赖：pymysql、redis、pika、python-dotenv、uvicorn、pydantic

## 业务流程
1. 用户请求下单接口，**Redis Lua脚本原子执行库存判断+预扣库存**，防止并发超卖。
2. MySQL写入订单记录，订单状态标记为「待扣库存」。
3. 向RabbitMQ发送持久化消息，携带唯一消息ID。
4. 消费者监听队列，收到消息后：
   - 利用消息记录表 `msg_record` 做幂等判断，避免重复消费多次扣库存。
   - Redis扣减库存，更新MySQL订单状态为成功。
   - 记录已处理消息ID，手动ACK确认消费完成。

## 核心亮点（面试高频）
1. **Redis Lua脚本**：单命令原子执行，解决并发超卖问题。
2. **RabbitMQ消息幂等**：数据库消息记录表，根据msg_id判断消息是否已处理，防止重复投递造成重复扣库存。
3. **消息持久化**：队列持久化 + 消息持久化，MQ重启不丢失消息。
4. **手动ACK**：业务处理完成后才ACK，防止消费者宕机导致消息丢失。
5. **参数校验 + 全局异常捕获**，接口健壮性更好。

## 项目目录结构
```

mall-order-service/
├─ venv/
├─ .env                 # 环境配置（不上传 git）
├─ .gitignore
├─ README.md
├─ create_tables.py     # 初始化数据库表
├─ main.py              # FastAPI 主服务（生产者）
└─ consumer.py          # RabbitMQ 消费者

```

## 环境准备
1. 本地启动 MySQL、Redis、RabbitMQ
2. 创建数据库 `mall_order`
3. 创建虚拟环境并安装依赖
```powershell
python -m venv venv
.\venv\Scripts\Activate
pip install fastapi uvicorn pymysql redis==3.5.3 pika python-dotenv
```

## 启动步骤

```
# 1. 创建数据表
python create_tables.py

# 2. Redis初始化库存
redis-cli
set stock:1 100

# 3. 启动FastAPI服务（终端A）
python main.py

# 4. 启动消费者（终端B）
python consumer.py
```

## 接口文档

访问：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
接口：POST /order/create
请求体示例：

```
{
  "product_id": 1,
  "buy_num": 2
}
```