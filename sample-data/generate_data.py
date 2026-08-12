# -*- coding: utf-8 -*-
"""
@brief 生成电商经营模拟测试数据（CSV 格式）

运行: python generate_data.py
生成: orders.csv / products.csv / customers.csv
说明: 数据均为程序生成的模拟数据，仅用于功能体验与测试。
"""

import csv
import random
import datetime

random.seed(42)

# ── 基础维度 ──
CATEGORIES = {
    "数码家电": ["无线蓝牙耳机", "智能手表", "便携充电宝", "4K 显示器", "机械键盘"],
    "服饰鞋包": ["纯棉 T 恤", "休闲运动鞋", "双肩背包", "牛仔裤", "羽绒服"],
    "美妆个护": ["保湿面霜", "防晒霜", "电动牙刷", "洗发水", "面膜"],
    "食品生鲜": ["坚果礼盒", "咖啡豆", "有机牛奶", "水果拼盘", "零食大礼包"],
    "家居生活": ["记忆枕", "保温杯", "香薰蜡烛", "四件套", "收纳箱"],
}

CHANNELS = ["天猫旗舰店", "京东自营", "抖音小店", "拼多多", "线下门店"]
CITIES = ["北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "南京", "苏州", "重庆"]
PAY_METHODS = ["支付宝", "微信支付", "银行卡", "花呗"]

# ── 商品列表 ──
products = []
for cat, names in CATEGORIES.items():
    for name in names:
        products.append({
            "商品ID": f"P{len(products) + 1:04d}",
            "商品名称": name,
            "类目": cat,
            "成本价": round(random.uniform(10, 300), 2),
        })

# ── 生成订单数据（2025-01 至 2025-06，约 600 行）──
orders = []
start = datetime.date(2025, 1, 1)
end = datetime.date(2025, 6, 30)
days = (end - start).days

for i in range(600):
    p = random.choice(products)
    price = round(random.uniform(20, 800), 2)
    qty = random.randint(1, 5)
    discount = random.choice([0.9, 0.95, 1.0, 0.85, 1.0])
    pay_amount = round(price * qty * discount, 2)
    cost = round(p["成本价"] * qty, 2)
    order_date = start + datetime.timedelta(days=random.randint(0, days))
    orders.append({
        "订单号": f"SO{20250000 + i}",
        "下单日期": order_date.strftime("%Y-%m-%d"),
        "商品ID": p["商品ID"],
        "商品名称": p["商品名称"],
        "类目": p["类目"],
        "销售渠道": random.choice(CHANNELS),
        "城市": random.choice(CITIES),
        "单价": price,
        "数量": qty,
        "实付金额": pay_amount,
        "成本": cost,
        "支付方式": random.choice(PAY_METHODS),
    })

# ── 生成客户数据（约 300 行）──
customers = []
for i in range(300):
    joined = start + datetime.timedelta(days=random.randint(0, days))
    customers.append({
        "客户ID": f"C{1000 + i}",
        "昵称": f"用户{random.randint(10000, 99999)}",
        "城市": random.choice(CITIES),
        "注册日期": joined.strftime("%Y-%m-%d"),
        "累计消费": round(random.uniform(50, 20000), 2),
        "订单数": random.randint(1, 60),
        "最近购买日期": (start + datetime.timedelta(days=random.randint(0, days))).strftime("%Y-%m-%d"),
        "会员等级": random.choice(["普通会员", "银卡会员", "金卡会员", "钻石会员"]),
    })


def write_csv(filename: str, rows: list):
    """写入 CSV（UTF-8 with BOM，兼容 Excel 中文显示）"""
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"已生成: {filename} ({len(rows)} 行)")


if __name__ == "__main__":
    write_csv("orders.csv", orders)
    write_csv("products.csv", products)
    write_csv("customers.csv", customers)
