"""
@brief 数据看板编排服务

根据多个数据源的字段语义，智能生成经营指标卡片与可视化图表，
按数据源分区并列组织，顶部生成 AI 经营解读。
"""

import logging
from typing import Dict, Any, List, Optional

import pandas as pd

from app.services.data_ingestion import read_datasource, infer_purpose
from app.core.database import SessionLocal
from app.models.data_source import DataSource
from app.services.field_roles import detect_field_roles
from app.agent.tools import ecommerce_metrics as em
from app.agent.tools import visualization as viz

logger = logging.getLogger(__name__)


def _build_kpis(
    df: pd.DataFrame,
    roles: Dict[str, Optional[str]],
    data_source_id: str,
) -> List[Dict[str, Any]]:
    """
    @brief 按字段可用性生成 KPI 指标卡片，缺字段自动跳过
    @param df DataFrame
    @param roles 字段角色映射
    @param data_source_id 数据源 ID
    @return KPI 卡片列表
    """
    kpis: List[Dict[str, Any]] = []
    amount_col = roles.get("amount")
    order_col = roles.get("order_id")
    customer_col = roles.get("customer_id")
    qty_col = roles.get("qty")

    if amount_col:
        total_amount = float(df[amount_col].dropna().sum())
        kpis.append({
            "key": "sales", "label": "销售额",
            "value": round(total_amount, 2), "unit": "元", "kind": "currency",
        })

    if order_col:
        order_count = int(df[order_col].dropna().nunique())
    else:
        order_count = len(df)
    kpis.append({
        "key": "orders", "label": "订单量",
        "value": order_count, "unit": "单", "kind": "number",
    })

    if amount_col:
        aov = em.ecommerce_metrics(data_source_id, "aov")
        if aov.get("success") and aov.get("value") is not None:
            kpis.append({
                "key": "aov", "label": "客单价",
                "value": aov["value"], "unit": "元", "kind": "currency",
            })

    if customer_col:
        customer_count = int(df[customer_col].dropna().nunique())
        kpis.append({
            "key": "customers", "label": "客户数",
            "value": customer_count, "unit": "人", "kind": "number",
        })

        rpr = em.ecommerce_metrics(data_source_id, "repeat_purchase_rate")
        if rpr.get("success") and rpr.get("value") is not None:
            kpis.append({
                "key": "repeat_rate", "label": "复购率",
                "value": round(rpr["value"] * 100, 2), "unit": "%", "kind": "percent",
            })

    if roles.get("status"):
        rr = em.ecommerce_metrics(data_source_id, "return_rate")
        if rr.get("success") and rr.get("value") is not None:
            kpis.append({
                "key": "return_rate", "label": "退货率",
                "value": round(rr["value"] * 100, 2), "unit": "%", "kind": "percent",
            })

    if amount_col and roles.get("cost"):
        pm = em.ecommerce_metrics(data_source_id, "profit_margin")
        if pm.get("success") and pm.get("value") is not None:
            kpis.append({
                "key": "profit_margin", "label": "毛利率",
                "value": round(pm["value"] * 100, 2), "unit": "%", "kind": "percent",
            })

    if qty_col:
        total_qty = float(df[qty_col].dropna().sum())
        kpis.append({
            "key": "sales_qty", "label": "销量",
            "value": round(total_qty, 2), "unit": "件", "kind": "number",
        })

    return kpis


def _safe_chart(data_source_id: str, **kwargs) -> Optional[Dict[str, Any]]:
    """
    @brief 安全生成图表，失败时返回 None
    @param data_source_id 数据源 ID
    @param kwargs 传给 visualization 的参数
    @return {"chart_type", "echarts_option"} 或 None
    """
    try:
        result = viz.visualization(data_source_id, **kwargs)
        option = result.get("echarts_option")
        if option is None:
            return None
        return {
            "chart_type": result.get("chart_type", kwargs.get("chart_type")),
            "echarts_option": option,
        }
    except Exception as e:
        logger.debug(f"图表生成跳过: {e}")
        return None


def _build_charts(
    df: pd.DataFrame,
    roles: Dict[str, Optional[str]],
    data_source_id: str,
) -> List[Dict[str, Any]]:
    """
    @brief 按字段可用性生成图表，缺字段自动跳过
    @param df DataFrame
    @param roles 字段角色映射
    @param data_source_id 数据源 ID
    @return 图表块列表，每项含 chart_type/title/echarts_option
    """
    charts: List[Dict[str, Any]] = []
    date_col = roles.get("date")
    amount_col = roles.get("amount")
    category_col = roles.get("category")
    geo_col = roles.get("geo")
    qty_col = roles.get("qty")

    if date_col and amount_col:
        item = _safe_chart(
            data_source_id, chart_type="line", x=date_col, y=amount_col,
        )
        if item:
            item["title"] = "销售趋势"
            charts.append(item)

    if category_col and amount_col:
        item = _safe_chart(
            data_source_id, chart_type="pie", category=category_col, value=amount_col,
        )
        if item:
            item["title"] = "品类销售额占比"
            charts.append(item)

    if geo_col and (amount_col or qty_col):
        val = amount_col or qty_col
        item = _safe_chart(
            data_source_id, chart_type="bar", x=geo_col, y=val,
        )
        if item:
            item["title"] = "地域分布"
            charts.append(item)

    if category_col and qty_col:
        item = _safe_chart(
            data_source_id, chart_type="bar", x=category_col, y=qty_col, top_n=10,
        )
        if item:
            item["title"] = "商品销量 TOP10"
            charts.append(item)

    return charts


def build_section(data_source_id: str) -> Dict[str, Any]:
    """
    @brief 生成单个数据源的分区看板
    @param data_source_id 数据源 ID
    @return 分区结构 {data_source_id, name, purpose, row_count, kpis, charts}
    @throws ValueError 数据源不存在时
    """
    df = read_datasource(data_source_id)

    name = ""
    purpose = ""
    column_mapping = None
    db = SessionLocal()
    try:
        source = db.query(DataSource).filter(DataSource.id == data_source_id).first()
        if source is not None:
            name = source.name
            purpose = infer_purpose(source.name, source.columns_meta)
            column_mapping = source.column_mapping
    finally:
        db.close()

    roles = detect_field_roles(df, column_mapping)
    kpis = _build_kpis(df, roles, data_source_id)
    charts = _build_charts(df, roles, data_source_id)

    return {
        "data_source_id": data_source_id,
        "name": name,
        "purpose": purpose,
        "row_count": len(df),
        "kpis": kpis,
        "charts": charts,
    }


def _build_insight_context(sections: List[Dict[str, Any]]) -> str:
    """
    @brief 将各分区 KPI 汇总为 AI 解读上下文
    @param sections 分区列表
    @return 上下文文本
    """
    lines = [f"共 {len(sections)} 个数据源："]
    for sec in sections:
        kpi_texts = []
        for kpi in sec.get("kpis", []):
            kpi_texts.append(f"{kpi['label']}{kpi['value']}{kpi.get('unit', '')}")
        kpi_summary = "，".join(kpi_texts) if kpi_texts else "无可用指标"
        lines.append(f"{sec.get('name')}（{sec.get('purpose') or '通用数据'}）：{kpi_summary}")
    return "\n".join(lines)


async def generate_insight(sections: List[Dict[str, Any]]) -> Dict[str, str]:
    """
    @brief 生成 AI 经营解读，无 Key 或失败时提示未接入 AI
    @param sections 分区列表
    @return {"text", "source"}，source 为 ai 或 unavailable
    """
    context = _build_insight_context(sections)
    try:
        from app.core.llm import get_llm

        llm = get_llm()
        messages = [
            {
                "role": "system",
                "content": (
                    "你是电商经营数据分析师。根据数据看板的核心指标，用中文输出一段不超过150字的经营解读，"
                    "覆盖整体表现、亮点与风险，语气专业克制，不要罗列序号。"
                ),
            },
            {"role": "user", "content": context},
        ]
        text = await llm.chat(messages)
        if text and text.strip():
            return {"text": text.strip(), "source": "ai"}
    except Exception as e:
        logger.warning(f"AI 解读生成失败: {e}")

    return {"text": "未接入 AI，无法生成经营解读。", "source": "unavailable"}


async def build_dashboard(data_source_ids: List[str]) -> Dict[str, Any]:
    """
    @brief 构建完整看板
    @param data_source_ids 数据源 ID 列表
    @return {"insight", "sections", "errors"}
    """
    sections: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []

    for ds_id in data_source_ids:
        try:
            sections.append(build_section(ds_id))
        except Exception as e:
            errors.append({"data_source_id": ds_id, "error": str(e)})

    insight = await generate_insight(sections)
    return {"insight": insight, "sections": sections, "errors": errors}
