"""
@brief 统计分析工具

提供常用统计计算：求和、均值、同比、环比、TOP-N 排名等。
基于 pandas DataFrame，操作已载入的数据。
"""

from typing import Dict, Any, Optional, List
import pandas as pd
from app.services.data_ingestion import read_datasource


def statistics(
    data_source_id: str,
    operation: str,
    column: Optional[str] = None,
    method: Optional[str] = "sum",
    group_by: Optional[str] = None,
    top_n: Optional[int] = None,
    top_order: Optional[str] = "desc",
    current_period: Optional[str] = None,
    compare_period: Optional[str] = None,
    date_column: Optional[str] = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    @brief 统计分析工具入口
    @param data_source_id 数据源 ID
    @param operation 操作类型: aggregate / top_n / compare / describe
    @param column 目标列名
    @param method 聚合方法: sum / mean / count / min / max / median / std
    @param group_by 分组列名
    @param top_n TOP-N 数量
    @param top_order 排序方向: asc / desc
    @param current_period 当前周期标识（如 "2025-06"）
    @param compare_period 对比周期标识（如 "2025-05"）
    @param date_column 日期列名（同比环比计算用）
    @return 统计结果
    """
    df = read_datasource(data_source_id)

    if operation == "aggregate":
        return _aggregate(df, column, method, group_by)
    elif operation == "top_n":
        return _top_n(df, column, top_n or 10, top_order or "desc")
    elif operation == "compare":
        return _compare(df, column, current_period, compare_period, date_column, method or "sum")
    elif operation == "describe":
        return _describe(df, column)
    else:
        raise ValueError(f"不支持的统计操作: {operation}，可用: aggregate / top_n / compare / describe")


def _aggregate(
    df: pd.DataFrame,
    column: Optional[str],
    method: str,
    group_by: Optional[str],
) -> Dict[str, Any]:
    """聚合统计"""
    numeric_df = df.select_dtypes(include=["number"])

    if group_by:
        actual_group = _find_column(df, group_by)
        if actual_group is None:
            raise ValueError(f"分组列 '{group_by}' 不存在")

        if column:
            actual_col = _find_column(df, column)
            if actual_col is None:
                raise ValueError(f"列 '{column}' 不存在")
            agg_func = _get_agg_func(method)
            result = df.groupby(actual_group)[actual_col].agg(agg_func).reset_index()
        else:
            agg_func = _get_agg_func(method)
            result = df.groupby(actual_group)[numeric_df.columns].agg(agg_func).reset_index()

        result.columns = [str(c) for c in result.columns]
        return {
            "type": "grouped_aggregate",
            "group_column": actual_group,
            "method": method,
            "data": result.fillna(0).to_dict(orient="records"),
            "columns": [str(c) for c in result.columns],
        }

    # 无分组：全局聚合
    if column:
        actual_col = _find_column(df, column)
        if actual_col is None:
            raise ValueError(f"列 '{column}' 不存在")
        agg_func = _get_agg_func(method)
        value = df[actual_col].dropna().agg(agg_func)
        return {
            "type": "scalar",
            "column": actual_col,
            "method": method,
            "value": round(float(value), 2) if pd.notna(value) else 0,
        }

    # 所有数值列全局聚合
    agg_func = _get_agg_func(method)
    result = numeric_df.agg(agg_func)
    return {
        "type": "multi_column",
        "method": method,
        "data": {str(k): round(float(v), 2) if pd.notna(v) else 0 for k, v in result.items()},
    }


def _top_n(
    df: pd.DataFrame,
    column: str,
    n: int,
    order: str,
) -> Dict[str, Any]:
    """TOP-N 排名"""
    actual_col = _find_column(df, column)
    if actual_col is None:
        raise ValueError(f"排序列 '{column}' 不存在")

    ascending = order.lower() == "asc"
    result = df.nlargest(n, actual_col) if not ascending else df.nsmallest(n, actual_col)
    return {
        "type": "top_n",
        "column": actual_col,
        "n": n,
        "order": order,
        "data": result.fillna(0).to_dict(orient="records"),
        "columns": [str(c) for c in result.columns],
    }


def _compare(
    df: pd.DataFrame,
    column: Optional[str],
    current_period: Optional[str],
    compare_period: Optional[str],
    date_column: Optional[str],
    method: str,
) -> Dict[str, Any]:
    """
    @brief 同比/环比计算
    通过日期列筛选两个时间段，计算指标变化率。
    """
    if not date_column or not current_period or not compare_period:
        return {
            "type": "compare",
            "error": "同比/环比需要指定 date_column、current_period、compare_period",
        }

    actual_date = _find_column(df, date_column)
    if actual_date is None:
        raise ValueError(f"日期列 '{date_column}' 不存在")

    # 尝试解析日期
    date_series = pd.to_datetime(df[actual_date], errors="coerce")

    # 按月份格式筛选
    cur_mask = date_series.dt.strftime("%Y-%m") == current_period
    comp_mask = date_series.dt.strftime("%Y-%m") == compare_period

    if column:
        actual_col = _find_column(df, column)
        if actual_col is None:
            raise ValueError(f"指标列 '{column}' 不存在")
        cur_value = df.loc[cur_mask, actual_col].agg(_get_agg_func(method))
        comp_value = df.loc[comp_mask, actual_col].agg(_get_agg_func(method))
    else:
        numeric_cols = df.select_dtypes(include=["number"]).columns
        cur_value = df.loc[cur_mask, numeric_cols].sum().sum()
        comp_value = df.loc[comp_mask, numeric_cols].sum().sum()

    cur_value = float(cur_value) if pd.notna(cur_value) else 0.0
    comp_value = float(comp_value) if pd.notna(comp_value) else 0.0

    if comp_value == 0:
        change_rate = None
    else:
        change_rate = round((cur_value - comp_value) / comp_value * 100, 2)

    return {
        "type": "compare",
        "current_period": current_period,
        "compare_period": compare_period,
        "current_value": round(cur_value, 2),
        "compare_value": round(comp_value, 2),
        "change_rate": change_rate,  # 百分比，正数增长，负数下降
        "change_label": f"{'+' if change_rate and change_rate > 0 else ''}{change_rate}%" if change_rate is not None else "N/A",
    }


def _describe(df: pd.DataFrame, column: Optional[str]) -> Dict[str, Any]:
    """描述性统计"""
    if column:
        actual_col = _find_column(df, column)
        if actual_col is None:
            raise ValueError(f"列 '{column}' 不存在")
        stats = df[actual_col].describe().to_dict()
        return {"type": "describe", "column": actual_col, "statistics": {str(k): round(float(v), 2) if isinstance(v, (int, float)) and pd.notna(v) else v for k, v in stats.items()}}

    numeric_df = df.select_dtypes(include=["number"])
    if numeric_df.empty:
        return {"type": "describe", "statistics": {}, "message": "无数值列可供分析"}
    stats = numeric_df.describe().to_dict()
    return {"type": "describe", "statistics": stats}


def _get_agg_func(method: str):
    """获取聚合函数名（pandas Series.agg 可直接使用字符串名）"""
    method_map = {
        "sum": "sum",
        "mean": "mean",
        "avg": "mean",
        "count": "count",
        "min": "min",
        "max": "max",
        "median": "median",
        "std": "std",
    }
    return method_map.get(method, "sum")


def _find_column(df: pd.DataFrame, target: str) -> Optional[str]:
    """模糊匹配列名"""
    target_lower = target.strip().lower()
    for col in df.columns:
        if str(col).lower() == target_lower:
            return str(col)
    for col in df.columns:
        if target_lower in str(col).lower():
            return str(col)
    return None
