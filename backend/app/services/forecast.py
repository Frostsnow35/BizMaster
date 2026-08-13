"""
@brief 预测分析服务

基于数据源历史序列，用移动平均或线性回归外推未来趋势，
并生成 AI 预测解读（无 Key 时提示未接入 AI）。
"""

import logging
from typing import Dict, Any, List, Optional

import pandas as pd
import numpy as np

from app.services.data_ingestion import read_datasource
from app.services.dashboard import detect_field_roles

logger = logging.getLogger(__name__)

# 指标映射：metric -> 展示名 / 取值列角色 / 聚合方式
_METRIC_MAP = {
    "sales": {"label": "销售额", "col_key": "amount", "agg": "sum"},
    "orders": {"label": "订单量", "col_key": "order_id", "agg": "nunique"},
    "qty": {"label": "销量", "col_key": "qty", "agg": "sum"},
}

# 方法映射：method -> 展示名
_METHOD_MAP = {
    "linear": "线性回归",
    "moving_avg": "移动平均",
}

# 时间粒度支持：'D' 日 / 'W' 周 / 'M' 月
_FREQ_MAP = {"D": "日", "W": "周", "M": "月"}


def detect_forecast_fields(df: pd.DataFrame) -> Dict[str, Optional[str]]:
    """
    @brief 识别预测所需的日期列与数值指标列
    @param df DataFrame
    @return {"date", "amount", "order_id", "qty"} 角色到列名的映射
    """
    roles = detect_field_roles(df)
    return {
        "date": roles.get("date"),
        "amount": roles.get("amount"),
        "order_id": roles.get("order_id"),
        "qty": roles.get("qty"),
    }


def build_time_series(
    df: pd.DataFrame,
    date_col: str,
    value_col: Optional[str],
    freq: str = "D",
    agg: str = "sum",
) -> Dict[str, Any]:
    """
    @brief 按时间粒度聚合历史序列
    @param df DataFrame
    @param date_col 日期列名
    @param value_col 取值列名（agg 为 count 时可为 None）
    @param freq 时间粒度：D/W/M
    @param agg 聚合方式：sum/nunique/count
    @return {"dates": [str], "values": [float]}
    @throws ValueError 序列聚合后为空时
    """
    ts = df[[date_col] + ([value_col] if value_col else [])].copy()
    ts[date_col] = pd.to_datetime(ts[date_col], errors="coerce")
    ts = ts.dropna(subset=[date_col])

    if ts.empty:
        raise ValueError("数据源缺少有效日期，无法构建时间序列")

    if agg == "count" or value_col is None:
        grouped = ts.groupby(pd.Grouper(key=date_col, freq=freq)).size()
    elif agg == "nunique":
        ts[value_col] = ts[value_col].astype(str)
        grouped = ts.groupby(pd.Grouper(key=date_col, freq=freq))[value_col].nunique()
    else:
        ts[value_col] = pd.to_numeric(ts[value_col], errors="coerce")
        ts = ts.dropna(subset=[value_col])
        if ts.empty:
            raise ValueError("数据源缺少有效数值，无法构建时间序列")
        grouped = ts.groupby(pd.Grouper(key=date_col, freq=freq))[value_col].sum()

    grouped = grouped.sort_index()
    dates = [d.strftime("%Y-%m-%d") for d in grouped.index]
    values = [round(float(v), 2) for v in grouped.tolist()]

    if not values:
        raise ValueError("聚合后无可用数据点，无法预测")

    return {"dates": dates, "values": values}


def _future_dates(last_date_str: str, periods: int, freq: str) -> List[str]:
    """
    @brief 生成未来时间轴标签
    @param last_date_str 历史序列最后日期（YYYY-MM-DD）
    @param periods 预测期数
    @param freq 时间粒度
    @return 未来日期字符串列表
    """
    last = pd.to_datetime(last_date_str)
    future = pd.date_range(start=last, periods=periods + 1, freq=freq)[1:]
    return [d.strftime("%Y-%m-%d") for d in future]


def forecast_series(series: List[float], periods: int, method: str) -> List[float]:
    """
    @brief 用移动平均或线性回归外推未来值
    @param series 历史数值序列
    @param periods 预测期数
    @param method 方法：linear / moving_avg
    @return 未来预测值列表（长度 periods）
    @throws ValueError 方法不支持或序列为空时
    """
    if method not in _METHOD_MAP:
        raise ValueError(f"不支持的预测方法: {method}，可用: {', '.join(_METHOD_MAP.keys())}")

    values = np.array([float(v) for v in series], dtype=float)
    n = len(values)
    if n == 0:
        raise ValueError("历史序列为空，无法预测")

    if method == "moving_avg":
        window = min(3, n)
        base = float(np.mean(values[-window:]))
        pred = np.full(periods, base)
    else:
        x = np.arange(n)
        slope, intercept = np.polyfit(x, values, 1)
        future_x = np.arange(n, n + periods)
        pred = slope * future_x + intercept

    # 销量/销售额/订单量不应为负，做下限截断
    pred = np.clip(pred, 0, None)
    return [round(float(v), 2) for v in pred]


def _build_insight_context(
    metric_label: str,
    method_label: str,
    periods: int,
    historical: List[float],
    predicted: List[float],
) -> str:
    """
    @brief 汇总预测结果为 AI 解读上下文
    @param metric_label 指标名称
    @param method_label 预测方法名称
    @param periods 预测期数
    @param historical 历史序列
    @param predicted 预测序列
    @return 上下文文本
    """
    hist_mean = float(np.mean(historical)) if historical else 0.0
    last_actual = historical[-1] if historical else 0.0
    first_pred = predicted[0] if predicted else 0.0
    last_pred = predicted[-1] if predicted else 0.0

    if last_pred > first_pred:
        trend = "上升"
    elif last_pred < first_pred:
        trend = "下降"
    else:
        trend = "平稳"

    return (
        f"指标：{metric_label}\n"
        f"预测方法：{method_label}\n"
        f"预测周期：未来 {periods} 期\n"
        f"历史数据点数：{len(historical)}\n"
        f"历史均值：{round(hist_mean, 2)}\n"
        f"历史末值：{round(last_actual, 2)}\n"
        f"预测首期：{round(first_pred, 2)}\n"
        f"预测末期：{round(last_pred, 2)}\n"
        f"预测趋势：{trend}"
    )


async def generate_forecast_insight(
    metric_label: str,
    method_label: str,
    periods: int,
    historical: List[float],
    predicted: List[float],
) -> Dict[str, str]:
    """
    @brief 生成 AI 预测解读，无 Key 或失败时提示未接入 AI
    @param metric_label 指标名称
    @param method_label 预测方法名称
    @param periods 预测期数
    @param historical 历史序列
    @param predicted 预测序列
    @return {"text", "source"}，source 为 ai 或 unavailable
    """
    context = _build_insight_context(metric_label, method_label, periods, historical, predicted)
    try:
        from app.core.llm import get_llm

        llm = get_llm()
        messages = [
            {
                "role": "system",
                "content": (
                    "你是电商经营数据分析师。根据给出的历史序列与预测结果，用中文输出一段不超过120字的预测解读，"
                    "说明趋势方向与经营建议，语气专业克制，不要罗列序号。"
                ),
            },
            {"role": "user", "content": context},
        ]
        text = await llm.chat(messages)
        if text and text.strip():
            return {"text": text.strip(), "source": "ai"}
    except Exception as e:
        logger.warning(f"AI 预测解读生成失败: {e}")

    return {"text": "未接入 AI，无法生成预测解读。", "source": "unavailable"}


async def build_forecast(
    data_source_id: str,
    metric: str,
    periods: int = 30,
    method: str = "linear",
    freq: str = "D",
) -> Dict[str, Any]:
    """
    @brief 生成预测结果
    @param data_source_id 数据源 ID
    @param metric 指标：sales/orders/qty
    @param periods 预测期数
    @param method 预测方法：linear/moving_avg
    @param freq 时间粒度：D/W/M
    @return 预测响应结构
    @throws ValueError 指标不支持、缺少必要列或序列为空时
    """
    if metric not in _METRIC_MAP:
        raise ValueError(f"不支持的指标: {metric}，可用: {', '.join(_METRIC_MAP.keys())}")
    if freq not in _FREQ_MAP:
        raise ValueError(f"不支持的时间粒度: {freq}，可用: {', '.join(_FREQ_MAP.keys())}")

    meta = _METRIC_MAP[metric]
    metric_label = meta["label"]
    method_label = _METHOD_MAP.get(method, method)

    df = read_datasource(data_source_id)
    fields = detect_forecast_fields(df)
    date_col = fields.get("date")
    if date_col is None:
        raise ValueError("数据源缺少日期列，无法进行趋势预测")

    # 确定取值列与聚合方式
    value_col = None
    agg = meta["agg"]
    if metric == "orders" and fields.get("order_id") is None:
        # 缺订单号列时退化为按行计数
        value_col = None
        agg = "count"
    else:
        value_col = fields.get(meta["col_key"])
        if value_col is None:
            raise ValueError(f"数据源缺少{metric_label}对应列，无法预测该指标")

    series = build_time_series(df, date_col, value_col, freq=freq, agg=agg)
    historical_dates = series["dates"]
    historical_values = series["values"]

    predicted = forecast_series(historical_values, periods, method)
    if metric == "orders":
        predicted = [round(v) for v in predicted]
    future_dates = _future_dates(historical_dates[-1], periods, freq)

    dates = historical_dates + future_dates
    actual = historical_values + [None] * periods
    forecast = [None] * len(historical_values) + predicted

    insight = await generate_forecast_insight(
        metric_label, method_label, periods, historical_values, predicted,
    )

    return {
        "metric": metric,
        "metric_label": metric_label,
        "method": method,
        "method_label": method_label,
        "periods": periods,
        "freq": freq,
        "freq_label": _FREQ_MAP[freq],
        "dates": dates,
        "actual": actual,
        "forecast": forecast,
        "insight": insight,
    }
