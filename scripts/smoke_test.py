"""端到端冒烟测试（需先启动 API 和两个消费者，并建议设置 ORDER_TIMEOUT_SECONDS=15）

    python scripts/smoke_test.py [--timeout 15]
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = "http://127.0.0.1:8000/api"


def call(method, path, body=None, ip="10.0.0.1"):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={"Content-Type": "application/json", "X-Forwarded-For": ip},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def stock_of(pid):
    return call("GET", f"/product/{pid}")[1]["data"]["stock"]


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + (f"  {extra}" if extra else ""))
    if not cond:
        check.failed += 1


check.failed = 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout", type=int, default=15, help="服务端 ORDER_TIMEOUT_SECONDS")
    args = ap.parse_args()

    # 找到「限量」商品（库存最少的那个）
    products = call("GET", "/product/list")[1]["data"]
    check("商品列表", len(products) > 0, f"{len(products)} 个商品")
    target = min(products, key=lambda p: p["stock"])
    pid, init_stock = target["id"], target["stock"]
    print(f"测试商品: {target['product_name']} id={pid} 库存={init_stock}")

    # 1. 下单 + 支付
    s, r = call("POST", "/order/create", {"user_id": 1, "product_id": pid, "buy_num": 1})
    check("下单成功", s == 200 and r["code"] == 0, r["msg"])
    oid = r["data"]["order_id"]
    check("Redis 库存已预扣", stock_of(pid) == init_stock - 1)
    s, r = call("GET", f"/order/{oid}")
    check("订单为待支付", r["data"]["status"] == 0)
    s, r = call("POST", f"/order/{oid}/pay")
    check("支付成功", r["data"]["status"] == 1)
    s, r = call("POST", f"/order/{oid}/pay")
    check("重复支付幂等", s == 200 and r["data"]["status"] == 1)
    s, r = call("POST", f"/order/{oid}/cancel")
    check("已支付订单不能取消", s == 409, r["msg"])

    # 2. 手动取消归还库存
    before = stock_of(pid)
    s, r = call("POST", "/order/create", {"user_id": 2, "product_id": pid, "buy_num": 1}, ip="10.0.0.2")
    oid2 = r["data"]["order_id"]
    s, r = call("POST", f"/order/{oid2}/cancel")
    check("手动取消成功", s == 200 and r["data"]["status"] == 3)
    check("取消后库存归还", stock_of(pid) == before)

    # 3. 并发防超卖：remaining 件库存，30 个不同用户同时抢 1 件
    remaining = stock_of(pid)

    def buy(i):
        return call("POST", "/order/create", {"user_id": 100 + i, "product_id": pid, "buy_num": 1}, ip=f"10.1.0.{i}")

    with ThreadPoolExecutor(max_workers=30) as pool:
        results = list(pool.map(buy, range(30)))
    ok_cnt = sum(1 for s, r in results if s == 200)
    lack_cnt = sum(1 for s, r in results if s == 409 and r["msg"] == "库存不足")
    check("并发下单成功数 == 剩余库存", ok_cnt == remaining, f"成功 {ok_cnt} / 库存 {remaining}")
    check("其余请求提示库存不足", lack_cnt == 30 - ok_cnt, f"{lack_cnt} 个")
    check("Redis 库存归零且不为负", stock_of(pid) == 0)

    # 4. 限流：同一 IP 连续请求
    limited = 0
    for i in range(15):
        s, r = call("POST", "/order/create", {"user_id": 500 + i, "product_id": pid, "buy_num": 1}, ip="10.2.0.1")
        limited += s == 429
    check("同一 IP 触发限流(429)", limited > 0, f"{limited}/15 次被限流")

    # 5. 超时关单
    print(f"等待 {args.timeout + 8} 秒，观察超时关单 ...")
    time.sleep(args.timeout + 8)
    orders = [call("GET", f"/order/{r['data']['order_id']}")[1]["data"] for s, r in results if s == 200]
    check("未支付订单全部超时关闭", all(o["status"] == 2 for o in orders), str([o["status"] for o in orders]))
    check("超时关单后库存归还", stock_of(pid) == remaining, f"库存={stock_of(pid)}")
    s, r = call("GET", "/order/list?user_id=1")
    check("订单列表查询", s == 200 and len(r["data"]) >= 1)

    print("\n全部通过" if not check.failed else f"\n{check.failed} 项失败")
    sys.exit(1 if check.failed else 0)


if __name__ == "__main__":
    main()
