"""
@brief 图表生成工具

根据数据和图表类型生成 ECharts option JSON，前端可直接渲染。
支持折线图、柱状图、饼图、散点图。
"""

from typing import Dict, Any, Optional, List
import re
import pandas as pd
from app.services.data_ingestion import read_datasource


def _is_identifier_column(col_values) -> bool:
    """检测列是否为标识符（客户ID、订单号等），不应作为图表分类列"""
    sample = [str(v) for v in col_values.dropna().head(20)]
    if not sample:
        return False
    # 模式1: C开头+数字 (C001, C1234)
    if sum(1 for v in sample if bool(re.match(r'^[A-Z]\d{2,}$', v))) >= len(sample) * 0.5:
        return True
    # 模式2: 纯数字ID (≥6位数字，每个值几乎唯一)
    if sum(1 for v in sample if bool(re.match(r'^\d{6,}$', v))) >= len(sample) * 0.7:
        return True
    # 模式3: UUID 或长哈希 (带连字符的长串)
    if sum(1 for v in sample if len(v) > 20 and '-' in v) >= len(sample) * 0.5:
        return True
    return False


def _is_text_column(df: pd.DataFrame, col) -> bool:
    """判断列是否为文本列（兼容 pandas 的 object 与 str dtype）"""
    return pd.api.types.is_string_dtype(df[col]) or str(df[col].dtype).startswith("datetime")


_GEO_KEYWORDS = ("城市", "省份", "地区", "区域", "地址", "省", "市", "city", "province", "region", "area", "district", "address")


def _find_geo_column(df: pd.DataFrame) -> Optional[str]:
    """查找地理语义列（城市/省份/地区等），优先作为分类维度"""
    for col in df.columns:
        col_lower = str(col).lower()
        if any(kw in col_lower for kw in _GEO_KEYWORDS):
            if _is_text_column(df, col) and not _is_identifier_column(df[col]):
                return str(col)
    return None


def _find_business_column(df: pd.DataFrame, exclude: Optional[str] = None) -> Optional[str]:
    """查找业务含义的文本分类列（低基数、非标识符），优先地理列"""
    # 先找地理列
    geo = _find_geo_column(df)
    if geo and geo != exclude:
        return geo
    # 再找低基数的非标识符文本列（分类数越少越有业务含义）
    best, best_nunique = None, None
    for col in df.columns:
        if str(col) == exclude:
            continue
        if _is_text_column(df, col):
            if _is_identifier_column(df[col]):
                continue
            n = df[col].nunique()
            if best_nunique is None or n < best_nunique:
                best, best_nunique = str(col), n
    return best


def visualization(
    data_source_id: str,
    chart_type: str,
    x: Optional[str] = None,
    y: Optional[str] = None,
    category: Optional[str] = None,
    value: Optional[str] = None,
    title: Optional[str] = None,
    group_by: Optional[str] = None,
    agg_method: Optional[str] = "sum",
    top_n: Optional[int] = None,
    sort_order: Optional[str] = "desc",
    indicator_name: Optional[str] = None,
    indicator_value: Optional[float] = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    @brief 图表生成工具入口
    @param data_source_id 数据源 ID
    @param chart_type 图表类型: line / bar / pie / scatter / treemap / indicator
    @param x X 轴列名（line/bar/scatter）
    @param y Y 轴列名（line/bar/scatter）
    @param category 分类列名（pie/treemap）
    @param value 值列名（pie/treemap）
    @param title 图表标题
    @param group_by 分组列（数据预处理）
    @param agg_method 聚合方法
    @param top_n 取前 N 条
    @param sort_order 排序方向: desc / asc
    @param indicator_name 指标名称（indicator 类型使用）
    @param indicator_value 指标值（indicator 类型使用，LLM 可据此绕过数据处理直接显示数值）
    @param kwargs 其他参数
    @return {"chart_type": str, "echarts_option": dict}
    """
    df = read_datasource(data_source_id)

    # 确定分类列
    if chart_type in ("pie", "treemap"):
        check_cat_col = _lookup_column(df, category) if category else _infer_axis(df, "string")
    else:
        check_cat_col = _lookup_column(df, x) if x else _infer_axis(df, "string")

    # ── 标识符列自动纠错（所有图表类型）：分类列是标识符（如客户ID、订单号）时，自动切换为业务列 ──
    if check_cat_col and chart_type in ("pie", "bar", "treemap", "line", "scatter"):
        raw_unique = df[str(check_cat_col)].nunique()
        if raw_unique > 30 and _is_identifier_column(df[str(check_cat_col)]):
            alt_col = _find_business_column(df, exclude=str(check_cat_col))
            if alt_col:
                if chart_type in ("pie", "treemap"):
                    category = alt_col
                else:
                    x = alt_col
                check_cat_col = alt_col

    # ── 分类列兜底（所有图表类型）：未指定分类列时，自动选择地理/业务列 ──
    if check_cat_col is None and chart_type != "indicator":
        check_cat_col = _find_business_column(df)
        if check_cat_col:
            if chart_type in ("pie", "treemap"):
                category = check_cat_col
            else:
                x = check_cat_col

    # 数据预处理：分组聚合 + TOP-N
    if group_by:
        from app.agent.tools.statistics import _find_column, _get_agg_func
        actual_group = _find_column(df, group_by)
        # 分组列是标识符列且唯一值过多时，纠正为业务列（避免按 300 个客户 ID 分组）
        if actual_group and df[str(actual_group)].nunique() > 30 and _is_identifier_column(df[str(actual_group)]):
            alt = _find_business_column(df, exclude=str(actual_group))
            if alt:
                actual_group = alt
                group_by = alt
        if actual_group:
            if value:
                actual_val = _find_column(df, value)
                if actual_val:
                    df = df.groupby(actual_group)[actual_val].agg(_get_agg_func(agg_method)).reset_index()
                    df.columns = [group_by, value]
            else:
                df = df.groupby(actual_group).size().reset_index(name="count")
                df.columns = [group_by, "count"]
                if not value:
                    value = "count"

    # ── 自动聚合：数据行数 > 20 且未指定 group_by 时，按标签列聚合求和 ──
    if not group_by and len(df) > 20:
        if chart_type in ("pie", "treemap"):
            auto_label = category or _infer_axis(df, "string")
            auto_val = value or _infer_axis(df, "number")
        else:
            auto_label = x or _infer_axis(df, "string")
            auto_val = y or value or _infer_axis(df, "number")
        lbl = _lookup_column(df, auto_label)
        vl = _lookup_column(df, auto_val)
        if lbl and vl:
            df = df.groupby(str(lbl))[str(vl)].sum().reset_index()
            df.columns = [str(lbl), str(vl)]

    # ── 通用去重：如果标签列仍有重复值，再聚合一次 ──
    if chart_type in ("pie", "treemap"):
        cat_col = category or _infer_axis(df, "string")
        val_col = value or _infer_axis(df, "number")
        actual_label = _lookup_column(df, cat_col)
        actual_num = _lookup_column(df, val_col)
    else:
        actual_label = _lookup_column(df, x) if x else _infer_axis(df, "string")
        actual_num = _lookup_column(df, y) if y else _infer_axis(df, "number")

    if actual_label and actual_num and df[str(actual_label)].duplicated().any():
        df = df.groupby(str(actual_label))[str(actual_num)].sum().reset_index()
        df.columns = [str(actual_label), str(actual_num)]

    # ── 数据质量自适应：根据数据特征自动调整图表参数，而不是报错 ──
    if actual_label and chart_type in ("line", "bar", "scatter"):
        x_col_name = str(actual_label)
        unique_count = df[x_col_name].nunique()
        # 检测 X 列是否为日期/时间列
        is_datetime = False
        try:
            pd.to_datetime(df[x_col_name], format="mixed", errors="raise")
            is_datetime = True
        except (ValueError, TypeError):
            x_lower = x_col_name.lower()
            if any(kw in x_lower for kw in ("date", "time", "日期", "时间", "月", "年", "day", "month", "year")):
                is_datetime = True

        # 折线图：X 不是时间列 → 自动降级为柱状图（折线不适合品类/地区等分类维度）
        if chart_type == "line" and not is_datetime and unique_count > 15:
            chart_type = "bar"

        # 折线图：数据点过多 → 自动加 dataZoom，不截断
        if chart_type == "line" and unique_count > 50 and not top_n:
            pass  # dataZoom 已在 _build_xy_chart 中自动添加，无需额外处理

        # 柱状图：分类过多 → 自动设置 top_n 聚焦重点
        if chart_type == "bar" and unique_count > 30 and not top_n:
            top_n = min(30, unique_count)

        # 散点图：数据点过多 → 自动取前 N
        if chart_type == "scatter" and unique_count > 30 and not top_n:
            top_n = min(50, unique_count)

    if top_n:
        ascending = sort_order.lower() == "asc"
        sort_col = _lookup_column(df, value) if value else None
        # xy 图表用 y 参数或推断的数值列
        if sort_col is None and chart_type in ("line", "bar", "scatter"):
            sort_col = _lookup_column(df, y) if y else actual_num
        # pie/treemap 用推断的数值列
        if sort_col is None:
            sort_col = actual_num
        if sort_col:
            df = df.nlargest(top_n, str(sort_col)) if not ascending else df.nsmallest(top_n, str(sort_col))

    # 生成 ECharts option
    if chart_type in ("line", "bar", "scatter"):
        option = _build_xy_chart(df, chart_type, x, y, title)
    elif chart_type == "pie":
        option = _build_pie_chart(df, category, value, title)
    elif chart_type == "treemap":
        option = _build_treemap_chart(df, category, value, title)
    elif chart_type == "indicator":
        option = _build_indicator_card(df, value, title, indicator_name, indicator_value)
    else:
        raise ValueError(f"不支持的图表类型: {chart_type}，可用: line / bar / pie / scatter / treemap / indicator")

    return {
        "chart_type": chart_type,
        "echarts_option": option,
    }


def _build_xy_chart(
    df: pd.DataFrame,
    chart_type: str,
    x: Optional[str],
    y: Optional[str],
    title: Optional[str],
) -> Dict[str, Any]:
    """构建直角坐标系图表（折线图/柱状图/散点图）"""
    # 智能推断 X 和 Y 轴；模糊匹配失败时回退到推断，避免 KeyError: 'None'
    actual_x = _lookup_column(df, x) if x else None
    if actual_x is None:
        actual_x = _infer_axis(df, prefer="string")
    actual_y = _lookup_column(df, y) if y else None
    if actual_y is None:
        actual_y = _infer_axis(df, prefer="number")

    x_data = df[str(actual_x)].astype(str).tolist()
    y_data = df[str(actual_y)].fillna(0).tolist()

    # 类型转换（日期或字符串为 X 轴）
    x_type = "category"
    try:
        pd.to_datetime(df[str(actual_x)], format="mixed", dayfirst=False)
        x_type = "time"
    except (ValueError, TypeError):
        pass

    option = {
        "textStyle": {"fontFamily": "PingFang SC, Microsoft YaHei, sans-serif"},
        "title": {"text": title or f"{actual_y} 分析", "left": "center"},
        "tooltip": {"trigger": "axis" if chart_type != "scatter" else "item"},
        "xAxis": {
            "type": x_type,
            "data": x_data if x_type == "category" else None,
            "axisLabel": {"rotate": 30 if len(x_data) > 6 else 0, "interval": 0},
        },
        "yAxis": {"type": "value", "name": str(actual_y)},
        "series": [
            {
                "name": str(actual_y),
                "type": chart_type,
                "data": y_data,
                "smooth": chart_type == "line",
                "symbolSize": 8 if chart_type == "scatter" else 4,
            }
        ],
    }

    if chart_type == "bar":
        option["series"][0]["itemStyle"] = {"color": "#6366f1"}
        option["series"][0]["barMaxWidth"] = 40

    # 数据点超过 6 个时，添加底部 dataZoom 滑块，默认显示前 40% 可视窗口
    if len(x_data) > 6:
        visible_pct = min(100, max(20, 40.0 / len(x_data) * 100))
        option["dataZoom"] = [
            {
                "type": "slider",
                "start": 0,
                "end": visible_pct,
                "height": 20,
                "bottom": 8,
            }
        ]
        option["grid"] = {"bottom": 50}

    return option


def _build_treemap_chart(
    df: pd.DataFrame,
    category: Optional[str],
    value: Optional[str],
    title: Optional[str],
) -> Dict[str, Any]:
    """构建矩形树图（treemap），展示品类占比层级结构"""
    actual_cat = _lookup_column(df, category) if category else None
    if actual_cat is None:
        actual_cat = _infer_axis(df, prefer="string")
    actual_val = _lookup_column(df, value) if value else None
    if actual_val is None:
        actual_val = _infer_axis(df, prefer="number")

    tree_data = []
    for _, row in df.iterrows():
        tree_data.append({
            "name": str(row[str(actual_cat)]),
            "value": float(row[str(actual_val)]) if pd.notna(row[str(actual_val)]) else 0,
        })

    option = {
        "textStyle": {"fontFamily": "PingFang SC, Microsoft YaHei, sans-serif"},
        "title": {"text": title or f"{actual_cat} 占比分布（矩形树图）", "left": "center"},
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
        "series": [
            {
                "type": "treemap",
                "data": tree_data,
                "label": {"show": True, "formatter": "{b}\n{d}%"},
                "itemStyle": {"borderColor": "#fff", "borderWidth": 1},
                "levels": [
                    {"colorSaturation": [0.35, 0.5]},
                    {"colorSaturation": [0.3, 0.45]},
                ],
            }
        ],
    }

    return option


def _build_indicator_card(
    df: pd.DataFrame,
    value_col: Optional[str],
    title: Optional[str],
    indicator_name: Optional[str] = None,
    indicator_value: Optional[float] = None,
) -> Dict[str, Any]:
    """构建指标卡（gauge 仪表盘），展示单一核心指标"""
    # 尝试从 DataFrame 提取指标值
    actual_val = None
    if indicator_value is not None:
        actual_val = indicator_value
    elif value_col:
        actual_col = _lookup_column(df, value_col)
        if actual_col:
            # 尝试从数值列取值：均值 > 求和 > 首行
            try:
                actual_val = float(df[str(actual_col)].mean())
            except Exception:
                actual_val = float(df[str(actual_col)].iloc[0]) if len(df) > 0 else 0

    if actual_val is None:
        # 兜底：取第一列数值列的均值
        for col in df.columns:
            if pd.api.types.is_numeric_dtype(df[col]):
                actual_val = float(df[col].mean())
                break

    if actual_val is None:
        actual_val = 0

    name = indicator_name or value_col or title or "指标"

    option = {
        "textStyle": {"fontFamily": "PingFang SC, Microsoft YaHei, sans-serif"},
        "title": {"text": title or name, "left": "center", "top": 10},
        "series": [
            {
                "type": "gauge",
                "center": ["50%", "60%"],
                "radius": "85%",
                "startAngle": 210,
                "endAngle": -30,
                "min": 0,
                "max": max(actual_val * 1.5, 100),
                "splitNumber": 5,
                "axisLine": {
                    "lineStyle": {
                        "width": 16,
                        "color": [[0.3, "#6366f1"], [0.7, "#8b5cf6"], [1, "#ec4899"]],
                    }
                },
                "pointer": {"length": "70%", "width": 6, "itemStyle": {"color": "auto"}},
                "detail": {
                    "valueAnimation": True,
                    "formatter": "{value}",
                    "fontSize": 28,
                    "offsetCenter": [0, "60%"],
                },
                "data": [{"value": round(actual_val, 2), "name": name}],
            }
        ],
    }

    return option


def _build_pie_chart(
    df: pd.DataFrame,
    category: Optional[str],
    value: Optional[str],
    title: Optional[str],
) -> Dict[str, Any]:
    """构建饼图：按值降序排列，分类数由数据本身决定，标题不重叠"""
    actual_cat = _lookup_column(df, category) if category else None
    if actual_cat is None:
        actual_cat = _infer_axis(df, prefer="string")
    actual_val = _lookup_column(df, value) if value else None
    if actual_val is None:
        actual_val = _infer_axis(df, prefer="number")

    # 构建饼图数据，按值降序
    pie_data = []
    for _, row in df.iterrows():
        v = float(row[str(actual_val)]) if pd.notna(row[str(actual_val)]) else 0
        if v > 0:
            pie_data.append({"name": str(row[str(actual_cat)]), "value": v})
    pie_data.sort(key=lambda x: x["value"], reverse=True)

    option = {
        "textStyle": {"fontFamily": "PingFang SC, Microsoft YaHei, sans-serif"},
        "title": {
            "text": title or f"{actual_cat} 占比分布",
            "left": "center",
            "top": 5,
            "textStyle": {"fontSize": 14},
        },
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
        "legend": {
            "orient": "horizontal",
            "bottom": 5,
            "type": "scroll",
            "textStyle": {"fontSize": 11},
        },
        "series": [
            {
                "name": str(actual_cat),
                "type": "pie",
                "radius": ["45%", "70%"],
                "center": ["50%", "50%"],
                "data": pie_data,
                "label": {
                    "formatter": "{b}\n{d}%",
                    "fontSize": 11,
                },
                "emphasis": {
                    "itemStyle": {
                        "shadowBlur": 10,
                        "shadowOffsetX": 0,
                        "shadowColor": "rgba(0, 0, 0, 0.5)",
                    }
                },
            }
        ],
    }

    return option


def _infer_axis(df: pd.DataFrame, prefer: str = "string") -> Optional[str]:
    """智能推断坐标轴列：优先地理列，其次低基数的非标识符文本列"""
    if prefer == "string":
        # 优先地理列（城市/省份/地区等）
        geo = _find_geo_column(df)
        if geo:
            return geo
        # 其次低基数的非标识符文本列（业务分类维度）
        best, best_nunique = None, None
        for col in df.columns:
            if _is_text_column(df, col):
                if _is_identifier_column(df[col]):
                    continue
                n = df[col].nunique()
                if best_nunique is None or n < best_nunique:
                    best, best_nunique = str(col), n
        if best:
            return best
        # 全部是标识符列时，退回第一个字符串列
        for col in df.columns:
            if _is_text_column(df, col):
                return str(col)
    elif prefer == "number":
        for col in df.columns:
            if pd.api.types.is_numeric_dtype(df[col]):
                return str(col)
    # 兜底
    return str(df.columns[0])


def _lookup_column(df: pd.DataFrame, target: str) -> Optional[str]:
    """模糊匹配列名：精确匹配优先；子串匹配时排除标识符列，避免「客户」命中「客户ID」"""
    target_lower = target.strip().lower()
    for col in df.columns:
        if str(col).lower() == target_lower:
            return str(col)
    for col in df.columns:
        if target_lower in str(col).lower():
            if _is_identifier_column(df[col]):
                continue
            return str(col)
    return None
