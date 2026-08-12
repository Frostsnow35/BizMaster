"""
@brief 数据校验器模块

对上传数据执行列类型推断、空值统计、异常值检测，生成校验报告。
"""
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np


def infer_column_types(df: pd.DataFrame) -> Dict[str, str]:
    """
    @brief 推断每列的语义类型
    @param df DataFrame
    @return {列名: 推断类型}，类型包括: date / datetime / number / integer / string / boolean
    """
    type_map = {}
    for col in df.columns:
        col_name = str(col)
        series = df[col].dropna()
        if len(series) == 0:
            type_map[col_name] = "string"
            continue

        # 尝试解析为日期
        if _is_date_column(series, col_name):
            type_map[col_name] = "date"
        elif pd.api.types.is_integer_dtype(series):
            type_map[col_name] = "integer"
        elif pd.api.types.is_float_dtype(series):
            type_map[col_name] = "number"
        elif pd.api.types.is_bool_dtype(series):
            type_map[col_name] = "boolean"
        else:
            type_map[col_name] = "string"

    return type_map


def _is_date_column(series: pd.Series, col_name: str) -> bool:
    """检测列是否为日期类型"""
    # 已知日期关键词
    date_keywords = ["日期", "时间", "date", "time", "datetime", "下单", "创建", "更新", "支付"]
    col_lower = col_name.lower()
    has_date_keyword = any(kw in col_lower for kw in date_keywords)

    # 如果已经是 datetime 类型
    if pd.api.types.is_datetime64_any_dtype(series):
        return True

    # 尝试解析为 datetime（兼容 pandas 的 object 与 str dtype）
    if series.dtype == "object" or pd.api.types.is_string_dtype(series):
        sample = series.head(20)
        try:
            pd.to_datetime(sample, errors="raise")
            return True
        except (ValueError, TypeError):
            pass

    return has_date_keyword and (pd.api.types.is_string_dtype(series) or series.dtype in ("int64", "float64"))


def detect_empty_values(df: pd.DataFrame) -> Dict[str, Any]:
    """
    @brief 空值统计检测
    @param df DataFrame
    @return {
        "total_rows": int,
        "empty_columns": [{"name": str, "null_count": int, "null_ratio": float}, ...],
        "overall_empty_rate": float,
    }
    """
    total_rows = len(df)
    empty_columns = []
    total_nulls = 0

    for col in df.columns:
        null_count = int(df[col].isnull().sum())
        total_nulls += null_count
        null_ratio = round(null_count / total_rows, 4) if total_rows > 0 else 0.0
        empty_columns.append({
            "name": str(col),
            "null_count": null_count,
            "null_ratio": null_ratio,
        })

    total_cells = total_rows * len(df.columns)
    overall_empty_rate = round(total_nulls / total_cells, 4) if total_cells > 0 else 0.0

    return {
        "total_rows": total_rows,
        "empty_columns": empty_columns,
        "overall_empty_rate": overall_empty_rate,
    }


def detect_outliers(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    @brief 异常值检测（IQR 方法）
    @param df DataFrame
    @return [{"column": str, "outlier_count": int, "outlier_ratio": float}, ...]
    """
    outliers = []
    numeric_cols = df.select_dtypes(include=[np.number]).columns

    for col in numeric_cols:
        series = df[col].dropna()
        if len(series) < 4:
            continue

        Q1 = series.quantile(0.25)
        Q3 = series.quantile(0.75)
        IQR = Q3 - Q1

        if IQR == 0:
            continue

        lower = Q1 - 1.5 * IQR
        upper = Q3 + 1.5 * IQR
        outlier_mask = (df[col] < lower) | (df[col] > upper)
        outlier_count = int(outlier_mask.sum())
        outlier_ratio = round(outlier_count / len(df), 4) if len(df) > 0 else 0.0

        if outlier_count > 0:
            outliers.append({
                "column": str(col),
                "outlier_count": outlier_count,
                "outlier_ratio": outlier_ratio,
            })

    return outliers


def validate_data(df: pd.DataFrame) -> Dict[str, Any]:
    """
    @brief 综合数据校验入口
    @param df DataFrame
    @return ValidationReport 字典 {
        "row_count": int,
        "column_count": int,
        "column_types": Dict,
        "empty_analysis": Dict,
        "outliers": List,
        "issues": List[str],
        "overall_score": float,  # 0-100 数据质量评分
    }
    """
    row_count = len(df)
    column_count = len(df.columns)
    column_types = infer_column_types(df)
    empty_analysis = detect_empty_values(df)
    outliers_list = detect_outliers(df)

    # 汇总问题
    issues = []
    for col_info in empty_analysis["empty_columns"]:
        if col_info["null_ratio"] > 0.3:
            issues.append(f"列 '{col_info['name']}' 空值率高达 {col_info['null_ratio']:.1%}")

    for out in outliers_list:
        if out["outlier_ratio"] > 0.05:
            issues.append(f"列 '{out['column']}' 存在 {out['outlier_count']} 个异常值 ({out['outlier_ratio']:.1%})")

    # 计算质量评分
    score = 100.0
    score -= empty_analysis["overall_empty_rate"] * 50  # 空值率惩罚
    for out in outliers_list:
        score -= out.get("outlier_ratio", 0) * 20  # 异常值惩罚
    overall_score = round(max(0.0, min(100.0, score)), 1)

    return {
        "row_count": row_count,
        "column_count": column_count,
        "column_types": column_types,
        "empty_analysis": empty_analysis,
        "outliers": outliers_list,
        "issues": issues,
        "overall_score": overall_score,
    }
