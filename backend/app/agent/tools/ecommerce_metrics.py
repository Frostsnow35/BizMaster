"""
@brief 电商核心指标计算工具

提供客单价、复购率、退货率、获客成本、广告回报率、客户生命周期价值、
库存周转率、毛利率、RFM分析共9项电商核心指标的计算能力。
基于 pandas DataFrame，操作已载入的数据源。
"""

from typing import Dict, Any, Optional
import pandas as pd
import numpy as np
from pydantic import BaseModel, Field
from app.services.data_ingestion import read_datasource


class EcommerceMetricsInput(BaseModel):
    """电商指标工具参数"""
    data_source_id: str = Field(description="数据源ID")
    operation: str = Field(description="指标类型: aov / repeat_purchase_rate / return_rate / cac / roas / ltv / inventory_turnover / profit_margin / rfm")
    group_by: str | None = Field(default=None, description="分组列名（return_rate 支持按此分组）")


# ============================================================
# 列名候选词库 —— 中英文混合，覆盖常见电商数据列命名
# ============================================================

_AMOUNT_CANDIDATES = [
    "金额", "amount", "price", "total", "实付", "支付金额",
    "订单金额", "总价", "成交价", "销售额", "销售金额",
    "revenue", "收入", "实付款", "应付金额", "单价",
]

_ORDER_ID_CANDIDATES = [
    "订单ID", "order_id", "订单号", "order", "订单编号",
    "交易号", "订单id", "ordernumber", "order_no", "orderno",
]

_CUSTOMER_ID_CANDIDATES = [
    "客户ID", "customer_id", "user_id", "买家ID", "会员ID",
    "用户ID", "buyer_id", "member_id", "客户编号", "买家",
    "客户", "用户名", "username",
]

_STATUS_CANDIDATES = [
    "状态", "退货", "退款", "return", "refund", "订单状态",
    "售后", "退货标记", "是否退货", "是否退款", "status",
    "order_status", "售后状态", "退货状态", "退款状态",
]

_AD_SPEND_CANDIDATES = [
    "广告花费", "ad_spend", "marketing_cost", "推广费",
    "营销费用", "广告费", "ad_cost", "市场费用", "推广费用",
    "营销费", "广告支出", "advertising", "广告投入",
]

_NEW_CUSTOMER_CANDIDATES = [
    "新客户", "new_customer", "is_new", "首次购买",
    "first_purchase", "新客", "是否新客", "客户类型",
    "新老客", "是否首单", "new_flag",
]

_SALES_VOLUME_CANDIDATES = [
    "销量", "销售数量", "quantity", "qty", "sales_volume",
    "销售件数", "数量", "售出数量", "购买数量", "volume",
]

_STOCK_CANDIDATES = [
    "库存", "stock", "inventory", "库存数量", "库存量",
    "当前库存", "可用库存", "stock_qty", "库存总数",
]

_COST_CANDIDATES = [
    "成本", "cost", "进价", "采购价", "进货价", "成本价",
    "单位成本", "unit_cost", "采购成本", "成本单价", "出厂价",
]

_DATE_CANDIDATES = [
    "日期", "date", "time", "下单时间", "购买日期",
    "订单日期", "交易时间", "支付时间", "创建时间",
    "datetime", "order_date", "create_time", "pay_time",
]

# 用于判断某行是否为退货/退款的关键词
_RETURN_KEYWORDS = ["退货", "退款", "return", "refund", "退", "售后", "已退"]


# ============================================================
# 列名自动检测
# ============================================================

def _detect_column(df: pd.DataFrame, candidates: list) -> Optional[str]:
    """
    @brief 自动检测 DataFrame 中的目标列
    @param df DataFrame
    @param candidates 候选列名列表（中英文混合）
    @return 匹配到的列名或 None

    匹配逻辑：先对每个候选做精确匹配（忽略大小写），
    再对每个候选做包含匹配（候选词是列名的子串，如 candidates=[金额] 匹配 "实付金额"）。
    """
    cols_raw = [str(c) for c in df.columns]
    cols_lower = [c.lower().strip() for c in cols_raw]

    # 第一轮：精确匹配
    for cand in candidates:
        cand_lower = cand.lower().strip()
        for i, col in enumerate(cols_lower):
            if col == cand_lower:
                return cols_raw[i]

    # 第二轮：包含匹配（候选词出现在列名中）
    for cand in candidates:
        cand_lower = cand.lower().strip()
        for i, col in enumerate(cols_lower):
            if cand_lower in col:
                return cols_raw[i]

    return None


# ============================================================
# 错误响应构建
# ============================================================

def _error_response(df: pd.DataFrame, missing_desc: str, required_hint: str) -> dict:
    """
    @brief 构建缺少必要列时的统一错误响应
    @param df DataFrame（用于列出当前所有列名）
    @param missing_desc 缺失列的中文描述
    @param required_hint 所需列的关键词提示
    @return 错误响应字典
    """
    return {
        "success": False,
        "error": f"缺少{missing_desc}（需包含 {required_hint} 或类似列），当前数据源列名：{list(df.columns)}",
    }


# ============================================================
# 主入口
# ============================================================

def ecommerce_metrics(
    data_source_id: str,
    operation: str,
    group_by: Optional[str] = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    @brief 电商核心指标计算工具入口
    @param data_source_id 数据源 ID
    @param operation 操作类型:
        aov                客单价
        repeat_purchase_rate 复购率
        return_rate        退货率（支持 group_by 按列分组）
        cac                获客成本
        roas               广告回报率
        ltv                客户生命周期价值
        inventory_turnover 库存周转率
        profit_margin      毛利率
        rfm                RFM客户分层分析
    @param group_by 分组列名（仅 return_rate 支持）
    @return 指标计算结果字典
    """
    try:
        df = read_datasource(data_source_id)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    if df.empty:
        return {"success": False, "error": "数据源为空，无法计算指标"}

    operation_map = {
        "aov": lambda: _calc_aov(df),
        "repeat_purchase_rate": lambda: _calc_repeat_purchase_rate(df),
        "return_rate": lambda: _calc_return_rate(df, group_by),
        "cac": lambda: _calc_cac(df),
        "roas": lambda: _calc_roas(df),
        "ltv": lambda: _calc_ltv(df),
        "inventory_turnover": lambda: _calc_inventory_turnover(df),
        "profit_margin": lambda: _calc_profit_margin(df),
        "rfm": lambda: _calc_rfm(df),
    }

    if operation not in operation_map:
        return {
            "success": False,
            "error": f"不支持的 operation: {operation}，可用: {', '.join(operation_map.keys())}",
        }

    try:
        return operation_map[operation]()
    except Exception as e:
        return {"success": False, "error": f"计算过程中发生异常: {str(e)}"}


# ============================================================
# 1. AOV 客单价
# ============================================================

def _calc_aov(df: pd.DataFrame) -> dict:
    """
    @brief 客单价 = 总金额 / 订单数
    """
    amount_col = _detect_column(df, _AMOUNT_CANDIDATES)
    if amount_col is None:
        return _error_response(df, "金额列", "金额/amount/price/revenue/实付")

    order_col = _detect_column(df, _ORDER_ID_CANDIDATES)
    total_amount = float(df[amount_col].dropna().sum())

    if order_col:
        order_count = int(df[order_col].dropna().nunique())
    else:
        order_count = len(df)

    if order_count == 0:
        return {
            "success": True,
            "metric": "客单价",
            "value": 0.0,
            "unit": "元",
            "total_amount": round(total_amount, 2),
            "order_count": 0,
        }

    aov = total_amount / order_count
    return {
        "success": True,
        "metric": "客单价",
        "value": round(aov, 2),
        "unit": "元",
        "total_amount": round(total_amount, 2),
        "order_count": order_count,
    }


# ============================================================
# 2. 复购率
# ============================================================

def _calc_repeat_purchase_rate(df: pd.DataFrame) -> dict:
    """
    @brief 复购率 = 购买次数 >= 2 的客户数 / 总购买客户数
    """
    cust_col = _detect_column(df, _CUSTOMER_ID_CANDIDATES)
    if cust_col is None:
        return _error_response(df, "客户ID列", "客户ID/customer_id/user_id/买家ID/会员ID")

    purchase_counts = df.groupby(cust_col).size()
    total_customers = len(purchase_counts)
    repeat_customers = int((purchase_counts >= 2).sum())

    if total_customers == 0:
        return {
            "success": True,
            "metric": "复购率",
            "value": 0.0,
            "unit": "%",
            "repeat_customers": 0,
            "total_customers": 0,
        }

    rate = repeat_customers / total_customers
    return {
        "success": True,
        "metric": "复购率",
        "value": round(rate, 4),
        "unit": "%",
        "repeat_customers": repeat_customers,
        "total_customers": total_customers,
    }


# ============================================================
# 3. 退货率
# ============================================================

def _calc_return_rate(df: pd.DataFrame, group_by: Optional[str] = None) -> dict:
    """
    @brief 退货率 = 退货/退款行数 / 总行数
    当指定 group_by 时，按该列分组计算各组退货率。
    """
    status_col = _detect_column(df, _STATUS_CANDIDATES)
    if status_col is None:
        return _error_response(df, "状态/退货标识列", "状态/退货/退款/return/refund/订单状态/售后")

    def _is_return(val) -> bool:
        """判断某个值是否表示退货/退款"""
        s = str(val).lower()
        return any(kw in s for kw in _RETURN_KEYWORDS)

    if group_by:
        actual_group = _detect_column(df, [group_by])
        if actual_group is None:
            # group_by 的值直接作为列名尝试精确/包含匹配均失败时，
            # 在 DataFrame 列中再做一次宽泛查找
            actual_group = _detect_column(df, [group_by])
        if actual_group is None:
            return _error_response(df, f"分组列 '{group_by}'", f"请确认列名，当前列: {list(df.columns)}")

        grouped = df.groupby(actual_group)
        result_groups = []
        for name, grp_df in grouped:
            total = len(grp_df)
            return_cnt = int(grp_df[status_col].apply(_is_return).sum())
            rate = return_cnt / total if total > 0 else 0.0
            result_groups.append({
                "group": str(name),
                "return_count": return_cnt,
                "total_count": total,
                "return_rate": round(rate, 4),
            })
        return {
            "success": True,
            "metric": "退货率（分组）",
            "unit": "%",
            "group_column": actual_group,
            "groups": result_groups,
        }

    # 不分组：全局退货率
    total_count = len(df)
    return_count = int(df[status_col].apply(_is_return).sum())
    rate = return_count / total_count if total_count > 0 else 0.0

    return {
        "success": True,
        "metric": "退货率",
        "value": round(rate, 4),
        "unit": "%",
        "return_count": return_count,
        "total_count": total_count,
    }


# ============================================================
# 4. CAC 获客成本
# ============================================================

def _calc_cac(df: pd.DataFrame) -> dict:
    """
    @brief 获客成本 = 总广告花费 / 新客户数
    若数据中无新客户标记列，返回提示信息。
    """
    ad_col = _detect_column(df, _AD_SPEND_CANDIDATES)
    if ad_col is None:
        return _error_response(df, "广告花费列", "广告花费/ad_spend/marketing_cost/推广费/营销费用")

    new_cust_col = _detect_column(df, _NEW_CUSTOMER_CANDIDATES)

    if new_cust_col is None:
        return {
            "success": False,
            "error": (
                "缺少新客户标记列，无法区分新老客户。"
                "请确保数据包含类似'新客户'/'is_new'/'是否新客'等列，"
                f"当前数据源列名：{list(df.columns)}"
            ),
        }

    total_spend = float(df[ad_col].dropna().sum())

    # 新客户标记可能是布尔值、0/1、或 "是"/"否" 等文本
    new_cust_series = df[new_cust_col]
    if pd.api.types.is_bool_dtype(new_cust_series) or pd.api.types.is_integer_dtype(new_cust_series):
        new_customers = int((new_cust_series > 0).sum())
    else:
        new_cust_str = new_cust_series.astype(str).str.lower().str.strip()
        new_customers = int(new_cust_str.isin(["是", "yes", "true", "1", "新客", "新客户", "new"]).sum())

    if new_customers == 0:
        return {
            "success": True,
            "metric": "获客成本",
            "value": None,
            "unit": "元/人",
            "total_spend": round(total_spend, 2),
            "new_customers": 0,
            "note": "新客户数为0，无法计算获客成本",
        }

    cac = total_spend / new_customers
    return {
        "success": True,
        "metric": "获客成本",
        "value": round(cac, 2),
        "unit": "元/人",
        "total_spend": round(total_spend, 2),
        "new_customers": new_customers,
    }


# ============================================================
# 5. ROAS 广告回报率
# ============================================================

def _calc_roas(df: pd.DataFrame) -> dict:
    """
    @brief 广告回报率 = 总销售收入 / 总广告花费
    """
    ad_col = _detect_column(df, _AD_SPEND_CANDIDATES)
    if ad_col is None:
        return _error_response(df, "广告花费列", "广告花费/ad_spend/marketing_cost/推广费/营销费用")

    amount_col = _detect_column(df, _AMOUNT_CANDIDATES)
    if amount_col is None:
        return _error_response(df, "收入/金额列", "金额/amount/revenue/收入/销售额")

    total_spend = float(df[ad_col].dropna().sum())
    total_revenue = float(df[amount_col].dropna().sum())

    if total_spend == 0:
        return {
            "success": True,
            "metric": "广告回报率",
            "value": None,
            "unit": "倍",
            "total_revenue": round(total_revenue, 2),
            "total_spend": round(total_spend, 2),
            "note": "广告花费为0，无法计算回报率",
        }

    roas = total_revenue / total_spend
    return {
        "success": True,
        "metric": "广告回报率",
        "value": round(roas, 2),
        "unit": "倍",
        "total_revenue": round(total_revenue, 2),
        "total_spend": round(total_spend, 2),
    }


# ============================================================
# 6. LTV 客户生命周期价值
# ============================================================

def _calc_ltv(df: pd.DataFrame) -> dict:
    """
    @brief 客户生命周期价值 = 总消费金额 / 总客户数
    """
    cust_col = _detect_column(df, _CUSTOMER_ID_CANDIDATES)
    if cust_col is None:
        return _error_response(df, "客户ID列", "客户ID/customer_id/user_id/买家ID/会员ID")

    amount_col = _detect_column(df, _AMOUNT_CANDIDATES)
    if amount_col is None:
        return _error_response(df, "金额列", "金额/amount/price/revenue/实付")

    total_amount = float(df[amount_col].dropna().sum())
    total_customers = int(df[cust_col].dropna().nunique())

    if total_customers == 0:
        return {
            "success": True,
            "metric": "客户生命周期价值",
            "value": 0.0,
            "unit": "元",
            "total_amount": round(total_amount, 2),
            "total_customers": 0,
        }

    ltv = total_amount / total_customers
    return {
        "success": True,
        "metric": "客户生命周期价值",
        "value": round(ltv, 2),
        "unit": "元",
        "total_amount": round(total_amount, 2),
        "total_customers": total_customers,
    }


# ============================================================
# 7. 库存周转率
# ============================================================

def _calc_inventory_turnover(df: pd.DataFrame) -> dict:
    """
    @brief 库存周转率 = 总销量 / 平均库存
    """
    sales_col = _detect_column(df, _SALES_VOLUME_CANDIDATES)
    if sales_col is None:
        return _error_response(df, "销量列", "销量/销售数量/quantity/qty/sales_volume")

    stock_col = _detect_column(df, _STOCK_CANDIDATES)
    if stock_col is None:
        return _error_response(df, "库存列", "库存/stock/inventory/库存数量")

    total_sales = float(df[sales_col].dropna().sum())
    avg_stock = float(df[stock_col].dropna().mean())

    if avg_stock == 0:
        return {
            "success": True,
            "metric": "库存周转率",
            "value": None,
            "unit": "次",
            "total_sales": round(total_sales, 2),
            "avg_stock": round(avg_stock, 2),
            "note": "平均库存为0，无法计算周转率",
        }

    turnover = total_sales / avg_stock
    return {
        "success": True,
        "metric": "库存周转率",
        "value": round(turnover, 2),
        "unit": "次",
        "total_sales": round(total_sales, 2),
        "avg_stock": round(avg_stock, 2),
    }


# ============================================================
# 8. 毛利率
# ============================================================

def _calc_profit_margin(df: pd.DataFrame) -> dict:
    """
    @brief 毛利率 = (收入 - 成本) / 收入 × 100%
    """
    amount_col = _detect_column(df, _AMOUNT_CANDIDATES)
    if amount_col is None:
        return _error_response(df, "收入/金额列", "金额/amount/revenue/收入")

    cost_col = _detect_column(df, _COST_CANDIDATES)
    if cost_col is None:
        return _error_response(df, "成本列", "成本/cost/进价/采购价")

    total_revenue = float(df[amount_col].dropna().sum())
    total_cost = float(df[cost_col].dropna().sum())

    if total_revenue == 0:
        return {
            "success": True,
            "metric": "毛利率",
            "value": None,
            "unit": "%",
            "total_revenue": round(total_revenue, 2),
            "total_cost": round(total_cost, 2),
            "note": "收入为0，无法计算毛利率",
        }

    margin = (total_revenue - total_cost) / total_revenue
    return {
        "success": True,
        "metric": "毛利率",
        "value": round(margin, 4),
        "unit": "%",
        "total_revenue": round(total_revenue, 2),
        "total_cost": round(total_cost, 2),
    }


# ============================================================
# 9. RFM 客户分层分析
# ============================================================

def _quantile_score(series: pd.Series, n: int = 3, ascending: bool = True) -> pd.Series:
    """
    @brief 将序列按分位数打分为 1~n
    @param series 待打分序列
    @param n 分档数，默认3
    @param ascending True 表示值越大得分越高
    @return 得分序列

    当序列唯一值不足 n 时自动降档处理：
    1 个唯一值 → 统一给中间分
    2 个唯一值 → 映射为最低分和最高分
    """
    unique_vals = series.nunique()
    if unique_vals <= 1:
        mid_score = (n + 1) // 2
        return pd.Series(mid_score, index=series.index)

    try:
        bins = pd.qcut(series, min(n, unique_vals), labels=False, duplicates="drop")
    except Exception:
        return pd.Series((n + 1) // 2, index=series.index)

    actual = bins.nunique()
    if actual <= 1:
        return pd.Series((n + 1) // 2, index=series.index)

    if ascending:
        if actual == 2:
            return bins * (n - 1) + 1  # 0→1, 1→n
        return bins + 1  # 0→1, 1→2, 2→3
    else:
        if actual == 2:
            return n - bins * (n - 1)  # 0→n, 1→1
        return n - bins  # 0→3, 1→2, 2→1


def _calc_rfm(df: pd.DataFrame) -> dict:
    """
    @brief RFM 客户分层分析

    Recency: 最后购买距今天数（以数据中最大日期为"今天"），分3档打分（3=最近）
    Frequency: 购买次数，分3档打分（3=最频繁）
    Monetary: 总消费金额，分3档打分（3=最高）

    综合分层：
      9分     高价值客户
      7-8分   重要发展客户
      5-6分   一般保持客户
      3-4分   需挽回客户
    """
    cust_col = _detect_column(df, _CUSTOMER_ID_CANDIDATES)
    if cust_col is None:
        return _error_response(df, "客户ID列", "客户ID/customer_id/user_id/买家ID/会员ID")

    date_col = _detect_column(df, _DATE_CANDIDATES)
    if date_col is None:
        return _error_response(df, "日期列", "日期/date/time/下单时间/购买日期/订单日期")

    amount_col = _detect_column(df, _AMOUNT_CANDIDATES)
    if amount_col is None:
        return _error_response(df, "金额列", "金额/amount/price/revenue/实付")

    # 构建 RFM 工作副本
    rfm_df = df[[cust_col, date_col, amount_col]].copy()
    rfm_df[date_col] = pd.to_datetime(rfm_df[date_col], errors="coerce")
    rfm_df = rfm_df.dropna(subset=[date_col, amount_col])

    if rfm_df.empty:
        return {"success": False, "error": "数据中无有效记录（日期或金额为空），无法进行 RFM 分析"}

    today = rfm_df[date_col].max()

    # 按客户聚合
    rfm = rfm_df.groupby(cust_col).agg(
        last_date=(date_col, "max"),
        frequency=(date_col, "count"),
        monetary=(amount_col, "sum"),
    ).reset_index()

    rfm["recency"] = (today - rfm["last_date"]).dt.days

    # 打分（Recency 越低越好 → ascending=False）
    rfm["R"] = _quantile_score(rfm["recency"], n=3, ascending=False)
    rfm["F"] = _quantile_score(rfm["frequency"], n=3, ascending=True)
    rfm["M"] = _quantile_score(rfm["monetary"], n=3, ascending=True)

    rfm["RFM_score"] = rfm["R"].astype(int) + rfm["F"].astype(int) + rfm["M"].astype(int)

    # 客户分层
    def _segment(score: int) -> str:
        if score >= 9:
            return "高价值客户"
        elif score >= 7:
            return "重要发展客户"
        elif score >= 5:
            return "一般保持客户"
        else:
            return "需挽回客户"

    rfm["segment"] = rfm["RFM_score"].apply(_segment)

    # 按分层汇总
    seg_stats = rfm.groupby("segment").agg(
        customer_count=("RFM_score", "count"),
        total_amount=("monetary", "sum"),
    ).reset_index()

    total_amount_all = float(seg_stats["total_amount"].sum())

    segments = []
    for _, row in seg_stats.iterrows():
        seg_name = str(row["segment"])
        seg_total = float(row["total_amount"])
        pct = (seg_total / total_amount_all * 100) if total_amount_all > 0 else 0.0
        segments.append({
            "segment": seg_name,
            "customer_count": int(row["customer_count"]),
            "total_amount": round(seg_total, 2),
            "amount_pct": round(pct, 2),
        })

    # 按指定顺序排列
    order = {"高价值客户": 0, "重要发展客户": 1, "一般保持客户": 2, "需挽回客户": 3}
    segments.sort(key=lambda x: order.get(x["segment"], 99))

    return {
        "success": True,
        "metric": "RFM客户分层分析",
        "total_customers": len(rfm),
        "total_amount": round(total_amount_all, 2),
        "scoring": {
            "R_range": f"{int(rfm['R'].min())}-{int(rfm['R'].max())}",
            "F_range": f"{int(rfm['F'].min())}-{int(rfm['F'].max())}",
            "M_range": f"{int(rfm['M'].min())}-{int(rfm['M'].max())}",
        },
        "segments": segments,
    }
