"""初始化数据库：建表 + 写入示例商品 + 预热 Redis 库存

用法：
    python create_tables.py            # 建表（已存在则跳过）并写入示例商品
    python create_tables.py --reset    # 删除旧表后重建（会清空订单和商品数据！）
"""
import sys

import pymysql
from sqlalchemy import inspect

import app.models  # noqa: F401  确保所有模型已注册到 Base
from app.core.config import settings
from app.core.mysql_client import Base, SessionLocal, engine
from app.core.redis_client import redis_client
from app.models.product import Product

SEED_PRODUCTS = [
    ("机械键盘", "87 键热插拔，青轴手感", "⌨️", 100, "299.00"),
    ("无线鼠标", "静音 2.4G，续航 12 个月", "🖱️", 200, "89.90"),
    ("27 寸显示器", "2K 165Hz IPS 电竞屏", "🖥️", 30, "1599.00"),
    ("降噪耳机", "主动降噪，蓝牙 5.3", "🎧", 50, "699.00"),
    ("限量秒杀 · 机械手表", "仅限 5 件，用来测试防超卖", "⌚", 5, "99.00"),
]


def ensure_database():
    conn = pymysql.connect(
        host=settings.MYSQL_HOST, port=settings.MYSQL_PORT,
        user=settings.MYSQL_USER, password=settings.MYSQL_PASSWORD, charset="utf8mb4",
    )
    with conn.cursor() as cur:
        cur.execute(
            f"CREATE DATABASE IF NOT EXISTS `{settings.MYSQL_DB}` DEFAULT CHARACTER SET utf8mb4"
        )
    conn.close()


def check_schema():
    """旧版本的 orders 表缺少新字段时给出提示"""
    insp = inspect(engine)
    for table in Base.metadata.sorted_tables:
        if not insp.has_table(table.name):
            continue
        existing = {c["name"] for c in insp.get_columns(table.name)}
        missing = {c.name for c in table.columns} - existing
        if missing:
            print(f"[错误] 表 {table.name} 是旧结构，缺少字段 {sorted(missing)}。")
            print("   请执行：python create_tables.py --reset  （会清空数据）")
            sys.exit(1)


def main():
    reset = "--reset" in sys.argv
    ensure_database()

    if reset:
        Base.metadata.drop_all(engine)
        print("[OK] 已删除旧表")
    else:
        check_schema()

    Base.metadata.create_all(engine)
    print("[OK] 表创建完成：product、orders、msg_record")

    with SessionLocal() as sess:
        if sess.query(Product).count() == 0:
            for name, desc, image, stock, price in SEED_PRODUCTS:
                sess.add(Product(product_name=name, description=desc, image=image, stock=stock, price=price))
            sess.commit()
            print(f"[OK] 已写入 {len(SEED_PRODUCTS)} 个示例商品")

        # 预热 Redis：清理旧缓存，并用 MySQL 库存覆盖 stock:{id}
        keys = []
        for pattern in ("product:*", "stock:*", "rate:*", "lock:*"):
            keys += redis_client.keys(pattern)
        if keys:
            redis_client.delete(*keys)
        for p in sess.query(Product).all():
            redis_client.set(f"stock:{p.id}", p.stock)
        print("[OK] Redis 库存已预热")


if __name__ == "__main__":
    main()
