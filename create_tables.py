import pymysql
from dotenv import load_dotenv
import os

load_dotenv()

conn = pymysql.connect(
    host=os.getenv("MYSQL_HOST"),
    port=int(os.getenv("MYSQL_PORT")),
    user=os.getenv("MYSQL_USER"),
    password=os.getenv("MYSQL_PASSWORD"),
    database=os.getenv("MYSQL_DB"),
    charset="utf8mb4"
)
cursor = conn.cursor()

# 订单表
sql_orders = """
CREATE TABLE IF NOT EXISTS orders (
    id INT PRIMARY KEY AUTO_INCREMENT,
    product_id INT NOT NULL,
    buy_num INT NOT NULL,
    status TINYINT DEFAULT 0 COMMENT '0待扣库存，1库存扣减成功',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""
cursor.execute(sql_orders)

# 消息幂等记录表
sql_msg_record = """
CREATE TABLE IF NOT EXISTS msg_record (
    id INT PRIMARY KEY AUTO_INCREMENT,
    msg_id VARCHAR(128) NOT NULL UNIQUE COMMENT '消息唯一ID',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""
cursor.execute(sql_msg_record)

conn.commit()
print("✅ orders订单表、msg_record幂等表创建成功！")

cursor.close()
conn.close()
