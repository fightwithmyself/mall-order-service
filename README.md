# mall-order-service 电商订单微服务

基于 **FastAPI + MySQL + Redis + RabbitMQ + Vue 3** 的电商下单系统，重点解决：并发超卖、消息重复消费、订单超时自动关闭。

## 技术栈

| 层 | 技术 | 作用 |
|---|---|---|
| 后端 | Python 3.10+ / FastAPI / SQLAlchemy 2 | REST 接口、ORM |
| 缓存 | Redis（3.2 及以上均可） | 商品缓存、库存预扣（Lua）、分布式锁、滑动窗口限流 |
| 消息 | RabbitMQ | 异步扣库存、TTL + 死信队列实现超时关单 |
| 数据库 | MySQL 8 | 订单、商品、消息幂等表 |
| 前端 | Vue 3 + Vite | 商品列表、下单、订单查询 / 支付 / 取消 |

## 业务流程

```
用户下单 POST /api/order/create
  │ ① 限流（Redis ZSET 滑动窗口，按 IP）
  │ ② 读商品缓存（防穿透 / 防击穿 / 防雪崩）
  │ ③ 分布式锁 lock:order:{user}:{product}（防重复提交）
  │ ④ Redis Lua 原子预扣库存（防超卖）
  │ ⑤ MySQL 写入「待支付」订单（失败则归还 Redis 库存）
  │ ⑥ 投递 MQ：扣库存消息 + 超时消息（投递失败则关单并归还库存）
  ▼
 stock_consumer：幂等地扣减 MySQL 库存（msg_record 唯一键 + 订单行锁）
 order_timeout_queue（TTL 30 分钟，无消费者）→ 过期 → dlx_exchange → dlq_order_timeout
 dlq_consumer：订单仍为待支付 → 关闭订单，归还 Redis / MySQL 库存
```

订单状态：`0 待支付` → `1 已支付`（POST pay）/ `2 超时关闭`（死信）/ `3 手动取消`。
支付、取消、超时关单、库存消费都用 `SELECT ... FOR UPDATE` 锁订单行，互斥且幂等。

## 目录结构

```
mall-order-service/
├─ main.py                  # FastAPI 入口：路由、CORS、全局异常
├─ create_tables.py         # 建表 + 示例商品 + Redis 库存预热（--reset 重建）
├─ start_all.ps1            # 本地一键启动（API + 2 个消费者 + 前端）
├─ scripts/smoke_test.py    # 端到端冒烟测试
├─ app/
│  ├─ api/                  # 路由：product.py、order.py
│  ├─ services/             # 业务：product_service.py（缓存/库存）、order_service.py（下单/支付/关单）
│  ├─ core/                 # config、mysql/redis/mq 客户端、redis_lock、rate_limiter、exceptions
│  ├─ models/ schemas/      # ORM 模型 / Pydantic 模型
│  └─ consumer/             # stock_consumer.py、dlq_consumer.py
└─ frontend/                # Vue 3 + Vite
```

## 本地运行

前提：本机已安装并启动 MySQL、Redis、RabbitMQ，Node.js 18+。

```powershell
# 1. 后端依赖
python -m venv venv
.\venv\Scripts\Activate
pip install -r requirements.txt

# 2. 配置：复制 .env.example 为 .env，填入本机 MySQL / RabbitMQ 账号密码
copy .env.example .env

# 3. 初始化数据库（建表、写入示例商品、预热 Redis 库存）
python create_tables.py

# 4. 前端依赖
cd frontend; npm install; cd ..

# 5. 一键启动（或分别在 4 个终端运行下面 4 条命令）
.\start_all.ps1
```

分别启动：

```powershell
python -m uvicorn main:app --port 8000 --reload     # API
python -m app.consumer.stock_consumer               # 库存消费者
python -m app.consumer.dlq_consumer                 # 死信（超时关单）消费者
cd frontend; npm run dev                            # 前端 http://localhost:5173
```

接口文档：<http://127.0.0.1:8000/docs>

## 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/product/list` | 商品列表（静态信息走缓存，库存取自 Redis） |
| GET | `/api/product/{id}` | 商品详情 |
| POST | `/api/order/create` | 下单 `{user_id, product_id, buy_num}`，限流 |
| GET | `/api/order/list?user_id=` | 用户订单列表 |
| GET | `/api/order/{id}` | 订单详情 |
| POST | `/api/order/{id}/pay` | 模拟支付 |
| POST | `/api/order/{id}/cancel` | 取消订单 |

统一响应：`{"code": 0, "msg": "...", "data": ...}`；失败时 `code` 等于 HTTP 状态码（404 / 409 库存不足或重复提交 / 429 限流 / 503 MQ 异常）。

## 调试超时关单

默认 30 分钟。调试时在 `.env` 加 `ORDER_TIMEOUT_SECONDS=15`，**并在 RabbitMQ 管理台（<http://127.0.0.1:15672>）先删除 `order_timeout_queue`**
（队列的 TTL 参数变了会报 `PRECONDITION_FAILED`），再重启 API 和消费者。然后：

```powershell
python scripts/smoke_test.py --timeout 15
```

脚本会验证：下单 / 支付 / 重复支付幂等 / 手动取消 / 并发防超卖 / 限流 / 超时关单与库存归还。

## 说明与取舍

- **库存一致性**：Redis 是下单时的库存准入（Lua 原子），MySQL 库存由消费者异步扣减，最终一致。Redis 数据丢失时，库存会在首次访问时从 MySQL 重新加载（`ensure_stock_loaded`）；也可重新执行 `create_tables.py` 预热。
- **限流 IP**：优先读取 `X-Forwarded-For`，为后续部署在 Nginx 后面准备；直接暴露公网时该头可被伪造，部署时需由 Nginx 覆盖。
- **用户体系**：当前没有登录，前端用「用户ID」输入框模拟。
