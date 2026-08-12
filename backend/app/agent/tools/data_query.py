"""
@brief 数据查询工具

支持对已入库数据源执行 SQL-like 查询、过滤、排序、分组聚合。
基于 pandas DataFrame，使用 duckdb 或纯 pandas 实现。
"""
from typing import Dict, Any, Optional
import json
import re
import pandas as pd
from app.services.data_ingestion import read_datasource


def _get_df(data_source_id: str) -> pd.DataFrame:
    """
    @brief 从 SQLite 加载数据源为 DataFrame
    @param data_source_id 数据源 ID
    @return DataFrame
    """
    return read_datasource(data_source_id)


def _get_join_df(data_source_id: str) -> pd.DataFrame:
    """
    @brief 从 SQLite 加载关联数据源为 DataFrame（JOIN 场景用）
    @param data_source_id 数据源 ID
    @return DataFrame
    """
    return read_datasource(data_source_id)


def _generate_short_id(data_source_id: str) -> str:
    """
    @brief 生成 duckdb 注册用的短表名
    取 data_source_id 前8位，替换非字母数字字符为下划线，加上 ds_ 前缀。
    @param data_source_id 数据源 ID
    @return 短表名（如 ds_abc12345）
    """
    short = data_source_id[:8]
    short = re.sub(r'[^a-zA-Z0-9]', '_', short)
    return f"ds_{short}"


def data_query(
    data_source_id: str,
    query: Optional[str] = None,
    operation: Optional[str] = None,
    column: Optional[str] = None,
    group_by: Optional[str] = None,
    agg_method: Optional[str] = "sum",
    filter_column: Optional[str] = None,
    filter_value: Optional[str] = None,
    filter_op: Optional[str] = "==",
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = "desc",
    limit: Optional[int] = 100,
    join_tables: Optional[list] = None,
    join_sql: Optional[str] = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    @brief 数据查询工具入口
    @param data_source_id 数据源 ID
    @param query SQL 查询语句（可选，优先使用）
    @param operation 操作类型: filter / group / sort
    @param column 操作的目标列
    @param group_by 分组列名
    @param agg_method 聚合方法: sum / mean / count / min / max
    @param filter_column 过滤列名
    @param filter_value 过滤值
    @param filter_op 过滤操作符: == / > / < / >= / <= / != / contains
    @param sort_by 排序列名
    @param sort_order 排序方向: asc / desc
    @param limit 返回行数上限
    @param join_tables 需要关联的其他数据源 ID 列表（可选）
    @param join_sql 带 JOIN 语法的 SQL（可选，不传时用基础 SQL + 表名替换）
    @return {"columns": [...], "data": [...], "row_count": int}
    """
    df = _get_df(data_source_id)

    # ---- 跨表 JOIN 查询分支 ----
    if join_tables:
        import duckdb

        errors = []

        # 注册主表
        duckdb.register("df", df)

        # 遍历注册关联表
        for jt_id in join_tables:
            short_name = _generate_short_id(jt_id)
            try:
                jt_df = _get_join_df(jt_id)
                duckdb.register(short_name, jt_df)
            except Exception as e:
                errors.append(f"加载关联表 {jt_id} 失败: {str(e)}")

        # 确定执行 SQL
        if join_sql:
            sql = join_sql
        elif query:
            sql = query
            # 替换 query 中的完整 data_source_id 为短表名
            for jt_id in join_tables:
                short_name = _generate_short_id(jt_id)
                if jt_id in sql:
                    sql = sql.replace(jt_id, short_name)
        else:
            return {
                "error": "join_tables 需要配合 join_sql 或 query 使用",
                "columns": [],
                "data": [],
                "row_count": 0,
            }

        try:
            result_df = duckdb.query(sql).to_df()
        except Exception as e:
            return {
                "error": f"JOIN 查询执行失败: {str(e)}",
                "columns": [],
                "data": [],
                "row_count": 0,
            }

        # 根据 operation 执行对应的 pandas 操作
        if operation == "filter" and filter_column:
            result_df = _filter_data(result_df, filter_column, filter_value, filter_op)
        elif operation == "group" and group_by:
            result_df = _group_data(result_df, group_by, column, agg_method, sort_by, sort_order, limit)
        elif operation == "sort" and sort_by:
            result_df = _sort_data(result_df, sort_by, sort_order, limit)

        # 限制返回行数
        if limit and len(result_df) > limit:
            result_df = result_df.head(limit)

        response = _df_to_response(result_df)
        if errors:
            response["errors"] = errors
        return response

    # ---- 原有单表查询分支（向后兼容，join_tables 为空时走此路径） ----
    # 如果有 SQL 查询，用 duckdb 执行
    if query:
        try:
            import duckdb
            result_df = duckdb.query(query).to_df()
        except (ImportError, Exception):
            # duckdb 不可用或 SQL 解析失败时，尝试简单解析
            result_df = _simple_query(df, query)
    else:
        result_df = df.copy()

    # 根据 operation 执行对应的 pandas 操作
    if operation == "filter" and filter_column:
        result_df = _filter_data(result_df, filter_column, filter_value, filter_op)
    elif operation == "group" and group_by:
        result_df = _group_data(result_df, group_by, column, agg_method, sort_by, sort_order, limit)
    elif operation == "sort" and sort_by:
        result_df = _sort_data(result_df, sort_by, sort_order, limit)

    # 限制返回行数
    if limit and len(result_df) > limit:
        result_df = result_df.head(limit)

    return _df_to_response(result_df)


def _filter_data(
    df: pd.DataFrame, col: str, value: str, op: str = "=="
) -> pd.DataFrame:
    """执行过滤操作"""
    # 自动匹配列名（模糊匹配）
    actual_col = _find_column(df, col)
    if actual_col is None:
        raise ValueError(f"列 '{col}' 不存在。可用列: {list(df.columns)}")

    if op in (">", "<", ">=", "<=", "==", "!="):
        try:
            num_val = float(value) if value else 0
            return df.query(f"`{actual_col}` {op} @num_val")
        except (ValueError, TypeError):
            # 降级为字符串比较
            pass

    if op == "contains":
        return df[df[actual_col].astype(str).str.contains(str(value), na=False)]

    # 默认等于比较
    return df[df[actual_col].astype(str) == str(value)]


def _group_data(
    df: pd.DataFrame,
    group_col: str,
    value_col: Optional[str],
    agg: str = "sum",
    sort_by: Optional[str] = None,
    sort_order: str = "desc",
    limit: Optional[int] = None,
) -> pd.DataFrame:
    """执行分组聚合"""
    actual_group = _find_column(df, group_col)
    if actual_group is None:
        raise ValueError(f"列 '{group_col}' 不存在。可用列: {list(df.columns)}")

    agg_map = {"sum": "sum", "mean": "mean", "count": "count", "min": "min", "max": "max"}
    agg_func = agg_map.get(agg, "sum")

    if value_col:
        actual_value = _find_column(df, value_col)
        if actual_value is None:
            raise ValueError(f"列 '{value_col}' 不存在。可用列: {list(df.columns)}")
        result = df.groupby(actual_group)[actual_value].agg(agg_func).reset_index()
    else:
        result = df.groupby(actual_group).size().reset_index(name="count")

    result.columns = [str(c) for c in result.columns]

    if sort_by:
        actual_sort = _find_column(result, sort_by)
        if actual_sort:
            ascending = sort_order.lower() != "desc"
            result = result.sort_values(by=actual_sort, ascending=ascending)

    if limit:
        result = result.head(limit)

    return result


def _sort_data(
    df: pd.DataFrame, col: str, order: str = "desc", limit: Optional[int] = None
) -> pd.DataFrame:
    """执行排序"""
    actual_col = _find_column(df, col)
    if actual_col is None:
        raise ValueError(f"列 '{col}' 不存在。可用列: {list(df.columns)}")
    ascending = order.lower() != "desc"
    result = df.sort_values(by=actual_col, ascending=ascending)
    if limit:
        result = result.head(limit)
    return result


def _simple_query(df: pd.DataFrame, query: str) -> pd.DataFrame:
    """
    @brief 简单自然语言查询解析（duckdb 不可用时的降级方案）
    支持的简单语法：SELECT ... FROM df WHERE ... GROUP BY ... ORDER BY ... LIMIT ...
    """
    query_lower = query.lower().strip()

    # WHERE 条件
    if "where" in query_lower:
        parts = query_lower.split("where", 1)
        condition = parts[1].strip().rstrip(";")
        # 简单解析：column op value
        import re
        match = re.match(r"`?(\w+)`?\s*(=|>|<|>=|<=|!=|like)\s*'?\"?([^';\"]+)'?\"?", condition)
        if match:
            col, op, val = match.group(1), match.group(2), match.group(3)
            actual_col = _find_column(df, col)
            if actual_col is None:
                return df
            if op == "like":
                return df[df[actual_col].astype(str).str.contains(val, na=False)]
            try:
                numeric_val = float(val)
                return df.query(f"`{actual_col}` {op} @numeric_val")
            except (ValueError, TypeError):
                return df[df[actual_col].astype(str) == val]

    return df


def _find_column(df: pd.DataFrame, target: str) -> Optional[str]:
    """
    @brief 模糊匹配列名
    先精确匹配，再尝试包含匹配，最后做相似度匹配。
    """
    target_lower = target.strip().lower()

    # 精确匹配
    for col in df.columns:
        if str(col).lower() == target_lower:
            return str(col)

    # 包含匹配
    for col in df.columns:
        col_lower = str(col).lower()
        if target_lower in col_lower or col_lower in target_lower:
            return str(col)

    # 单字匹配（如 "金额" 匹配 "实付金额"）
    for col in df.columns:
        col_lower = str(col).lower()
        chars = list(target_lower)
        if sum(1 for c in chars if c in col_lower) >= len(chars) * 0.6:
            return str(col)

    return None


def _df_to_response(df: pd.DataFrame) -> Dict[str, Any]:
    """
    @brief DataFrame 转为标准响应格式
    """
    # 处理日期列
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].astype(str)

    # 替换 NaN
    df = df.fillna(0)

    return {
        "columns": [str(c) for c in df.columns],
        "data": df.to_dict(orient="records"),
        "row_count": len(df),
    }
