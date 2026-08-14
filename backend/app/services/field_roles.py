"""
@brief 统一字段角色标准

定义数据源字段的语义角色，作为「字段映射确认」与「自动识别」的唯一标准。
看板、预测、指标计算均通过本模块解析字段角色，避免各处重复猜测。

column_mapping 的取值既可能是角色键（用户确认后保存），
也可能是平台标准列名（match_platform 自动匹配产出），本模块做双向兼容。
"""

from typing import Dict, List, Optional

import pandas as pd


# 字段角色定义：顺序即自动识别的优先级（更具体的角色在前）
FIELD_ROLES: List[Dict] = [
    {"key": "order_id", "label": "订单号", "candidates": [
        "订单号", "订单编号", "订单ID", "订单id", "交易号",
        "order_id", "orderno", "order_no", "ordernumber",
    ]},
    {"key": "date", "label": "日期/时间", "candidates": [
        "日期", "下单时间", "支付时间", "创建时间", "交易时间",
        "购买日期", "订单日期", "order_date", "create_time", "pay_time",
        "order_time", "payment_time", "datetime", "date", "time",
    ]},
    {"key": "amount", "label": "金额/销售额", "candidates": [
        "销售额", "销售金额", "订单金额", "实付金额", "实付款", "应付金额",
        "支付金额", "成交价", "总价", "金额", "revenue", "paid_amount",
        "amount", "price", "total",
    ]},
    {"key": "customer_id", "label": "客户标识", "candidates": [
        "客户ID", "买家ID", "会员ID", "用户ID", "客户编号", "客户姓名",
        "买家会员名", "买家昵称", "客户", "买家", "用户名",
        "customer_id", "user_id", "buyer_id", "member_id", "customer_name",
        "customer_account", "username",
    ]},
    {"key": "qty", "label": "销量/数量", "candidates": [
        "销量", "销售数量", "销售件数", "购买数量", "售出数量", "数量",
        "quantity", "qty", "sales_volume", "volume",
    ]},
    {"key": "status", "label": "订单/售后状态", "candidates": [
        "订单状态", "售后状态", "退货", "退款", "状态",
        "order_status", "return", "refund", "status",
    ]},
    {"key": "cost", "label": "成本", "candidates": [
        "成本", "进价", "采购价", "进货价", "成本价", "单位成本",
        "采购成本", "成本单价", "出厂价", "cost", "unit_cost",
    ]},
    {"key": "unit_price", "label": "单价", "candidates": [
        "单价", "商品单价", "成交单价", "unit_price",
    ]},
    {"key": "product_name", "label": "商品名称", "candidates": [
        "商品名称", "商品标题", "货品", "品名", "product_name", "product",
    ]},
    {"key": "category", "label": "品类/类目", "candidates": [
        "品类", "类目", "分类", "category", "cat", "sku",
    ]},
    {"key": "geo", "label": "地区", "candidates": [
        "省份", "城市", "地区", "区域", "收货地址", "地址", "省", "市",
        "province", "city", "region", "area", "district", "address",
    ]},
]

# 平台标准列名 → 角色键（兼容 match_platform 自动匹配产出的英文映射）
STANDARD_TO_ROLE: Dict[str, str] = {
    "order_id": "order_id",
    "amount": "amount",
    "paid_amount": "amount",
    "quantity": "qty",
    "order_time": "date",
    "payment_time": "date",
    "order_status": "status",
    "customer_name": "customer_id",
    "customer_account": "customer_id",
    "receiver_name": "customer_id",
    "receiver_address": "geo",
    "product_name": "product_name",
    "unit_price": "unit_price",
}

_ROLE_KEYS = {r["key"] for r in FIELD_ROLES}


def get_role_meta(role_key: str) -> Optional[Dict]:
    """
    @brief 获取角色定义元信息
    @param role_key 角色键
    @return 角色定义字典或 None
    """
    for r in FIELD_ROLES:
        if r["key"] == role_key:
            return r
    return None


def _to_role_key(value: str) -> Optional[str]:
    """
    @brief 将 column_mapping 的值归一化为角色键
    @param value 角色键或平台标准列名
    @return 角色键或 None（未识别）
    """
    if not value:
        return None
    if value in _ROLE_KEYS:
        return value
    return STANDARD_TO_ROLE.get(value)


def _find_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    """
    @brief 从候选词库中匹配 DataFrame 列名
    @param df DataFrame
    @param candidates 候选词列表（中英文混合）
    @return 匹配到的列名或 None

    匹配策略：先精确匹配，再做包含匹配。
    """
    cols_lower = {str(c).lower().strip(): str(c) for c in df.columns}

    for cand in candidates:
        key = cand.lower().strip()
        if key in cols_lower:
            return cols_lower[key]

    for cand in candidates:
        key = cand.lower().strip()
        for col_lower, col in cols_lower.items():
            if key in col_lower:
                return col

    return None


def detect_field_roles(
    df: pd.DataFrame,
    column_mapping: Optional[Dict[str, str]] = None,
) -> Dict[str, Optional[str]]:
    """
    @brief 解析 DataFrame 的字段角色
    @param df DataFrame
    @param column_mapping 列名映射 {原始列名: 角色键或平台标准列名}，优先使用
    @return 角色映射 {角色键: 列名或 None}

    优先使用用户确认过或平台匹配出的 column_mapping，缺失角色再用候选词补全。
    """
    roles: Dict[str, Optional[str]] = {r["key"]: None for r in FIELD_ROLES}

    # 1. 优先消费 column_mapping（用户确认或平台匹配结果）
    if column_mapping:
        df_cols = {str(c) for c in df.columns}
        for orig_col, std in column_mapping.items():
            role_key = _to_role_key(std)
            if not role_key:
                continue
            col_str = str(orig_col)
            if col_str in df_cols and roles.get(role_key) is None:
                roles[role_key] = col_str

    # 2. 缺失角色用候选词补全（仅兜底，不覆盖已确认结果）
    for r in FIELD_ROLES:
        if roles[r["key"]] is None:
            roles[r["key"]] = _find_col(df, r["candidates"])

    return roles


def suggest_field_mapping(
    df: pd.DataFrame,
    column_mapping: Optional[Dict[str, str]] = None,
) -> Dict[str, Optional[str]]:
    """
    @brief 生成前端字段映射确认界面所需的建议映射
    @param df DataFrame
    @param column_mapping 已有的列名映射（可选）
    @return {列名: 建议角色键或 None}
    """
    roles = detect_field_roles(df, column_mapping)
    col_to_role: Dict[str, Optional[str]] = {}
    for role_key, col in roles.items():
        if col:
            col_to_role[str(col)] = role_key
    return col_to_role
