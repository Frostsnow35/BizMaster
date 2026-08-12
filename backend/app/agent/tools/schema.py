"""
@brief 工具注册表

以 LangChain Tool 格式注册所有分析工具，供 Agent 状态图使用。
"""

from typing import List
from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool

from app.agent.tools.data_query import data_query
from app.agent.tools.statistics import statistics
from app.agent.tools.visualization import visualization
from app.agent.tools.data_source_search import search_data_sources
from app.agent.tools.ecommerce_metrics import ecommerce_metrics, EcommerceMetricsInput


# ── 工具参数 Schema ──

class DataQueryInput(BaseModel):
    """数据查询工具参数"""
    data_source_id: str = Field(description="数据源ID")
    query: str | None = Field(default=None, description="SQL查询语句（可选）")
    operation: str | None = Field(default=None, description="操作类型: filter / group / sort")
    column: str | None = Field(default=None, description="目标列名")
    group_by: str | None = Field(default=None, description="分组列名")
    agg_method: str | None = Field(default="sum", description="聚合方法: sum / mean / count / min / max")
    filter_column: str | None = Field(default=None, description="过滤列名")
    filter_value: str | None = Field(default=None, description="过滤值")
    filter_op: str | None = Field(default="==", description="过滤操作符: == / > / < / >= / <= / != / contains")
    sort_by: str | None = Field(default=None, description="排序列名")
    sort_order: str | None = Field(default="desc", description="排序方向: asc / desc")
    limit: int | None = Field(default=100, description="返回行数上限")


class StatisticsInput(BaseModel):
    """统计分析工具参数"""
    data_source_id: str = Field(description="数据源ID")
    operation: str = Field(description="操作类型: aggregate / top_n / compare / describe")
    column: str | None = Field(default=None, description="目标列名")
    method: str | None = Field(default="sum", description="聚合方法: sum / mean / count / min / max / median / std")
    group_by: str | None = Field(default=None, description="分组列名")
    top_n: int | None = Field(default=None, description="TOP-N 数量")
    top_order: str | None = Field(default="desc", description="排序方向: asc / desc")
    current_period: str | None = Field(default=None, description='当前周期如 "2025-06"')
    compare_period: str | None = Field(default=None, description='对比周期如 "2025-05"')
    date_column: str | None = Field(default=None, description="日期列名")


class VisualizationInput(BaseModel):
    """图表生成工具参数"""
    data_source_id: str = Field(description="数据源ID")
    chart_type: str = Field(description="图表类型: line(折线图) / bar(柱状图) / pie(饼图) / scatter(散点图) / treemap(矩形树图) / indicator(指标卡)")
    x: str | None = Field(default=None, description="X轴列名")
    y: str | None = Field(default=None, description="Y轴列名")
    category: str | None = Field(default=None, description="分类列名（饼图用）")
    value: str | None = Field(default=None, description="值列名（饼图用）")
    title: str | None = Field(default=None, description="图表标题")
    group_by: str | None = Field(default=None, description="分组列名（预处理）")
    agg_method: str | None = Field(default="sum", description="聚合方法")
    top_n: int | None = Field(default=None, description="取前N条")
    sort_order: str | None = Field(default="desc", description="排序方向")


class DataSourceSearchInput(BaseModel):
    """数据源搜索工具参数"""
    keywords: str = Field(description="搜索关键词（空格或逗号分隔），如 '客户 会员' 或 '商品,SKU'")


class EcommerceMetricsInput(BaseModel):
    """电商指标工具参数"""
    data_source_id: str = Field(description="数据源ID")
    operation: str = Field(
        description="指标类型: aov(客单价) / repeat_purchase_rate(复购率) / return_rate(退货率) / "
        "cac(获客成本) / roas(广告回报率) / ltv(客户生命周期价值) / "
        "inventory_turnover(库存周转率) / profit_margin(毛利率) / rfm(客户分层)"
    )
    group_by: str | None = Field(default=None, description="分组列名（return_rate 支持按此分组）")


# ── 工具注册 ──

def get_all_tools() -> List[StructuredTool]:
    """
    @brief 获取所有已注册的分析工具
    @return LangChain StructuredTool 列表
    """
    return [
        StructuredTool.from_function(
            func=data_query,
            name="data_query",
            description=(
                "数据查询工具。用于从数据源中查询、过滤、分组、排序数据。"
                "支持 SQL-like 查询和结构化操作。"
                "参数：data_source_id(必填), operation(filter/group/sort), "
                "column, group_by, agg_method, filter_column, filter_value, "
                "filter_op, sort_by, sort_order, limit"
            ),
            args_schema=DataQueryInput,
        ),
        StructuredTool.from_function(
            func=statistics,
            name="statistics",
            description=(
                "统计分析工具。用于执行统计分析，包括："
                "aggregate(聚合统计-sum/mean/count/min/max), "
                "top_n(TOP-N排名), compare(同比/环比计算), describe(描述性统计)。"
                "参数：data_source_id(必填), operation(必填), column, method, "
                "group_by, top_n, current_period, compare_period, date_column"
            ),
            args_schema=StatisticsInput,
        ),
        StructuredTool.from_function(
            func=visualization,
            name="visualization",
            description=(
                "图表生成工具。根据数据生成 ECharts 图表配置。"
                "支持 line(折线图)、bar(柱状图)、pie(饼图)、scatter(散点图)。"
                "参数：data_source_id(必填), chart_type(必填), x, y, "
                "category, value, title, group_by, agg_method, top_n"
            ),
            args_schema=VisualizationInput,
        ),
        StructuredTool.from_function(
            func=search_data_sources,
            name="search_data_sources",
            description=(
                "数据源搜索工具。在当前资源库中按关键词搜索匹配的数据源表。"
                "当单表无法满足分析需求时使用。"
                "参数：keywords(必填，空格或逗号分隔的搜索关键词)。"
                "返回匹配的数据源列表，含名称、用途、列名、行数。"
            ),
            args_schema=DataSourceSearchInput,
        ),
        StructuredTool.from_function(
            func=ecommerce_metrics,
            name="ecommerce_metrics",
            description=(
                "电商指标计算工具。用于直接计算电商核心经营指标，无需手写SQL公式。"
                "支持指标：aov(客单价=总额/订单数)、repeat_purchase_rate(复购率=复购客户/总客户)、"
                "return_rate(退货率=退货数/总数)、cac(获客成本=广告费/新客数)、"
                "roas(广告回报率=收入/广告费)、ltv(客户生命周期价值=总消费/总客户)、"
                "inventory_turnover(库存周转率=销量/平均库存)、profit_margin(毛利率)、"
                "rfm(客户分层：高价值/重要发展/一般保持/需挽回四层)。"
                "参数：data_source_id(必填), operation(必填), group_by(可选，退货率分组用)。"
                "当用户问题涉及以上任一指标时，优先使用本工具。"
            ),
            args_schema=EcommerceMetricsInput,
        ),
    ]
