"""
@brief 工具集单元测试
"""
import pytest
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def sample_df():
    """创建模拟电商数据"""
    return pd.DataFrame({
        "订单号": ["ORD001", "ORD002", "ORD003", "ORD004", "ORD005"],
        "下单日期": ["2025-06-01", "2025-06-02", "2025-06-03", "2025-05-01", "2025-05-02"],
        "金额": [100.0, 200.0, 150.0, 300.0, 50.0],
        "品类": ["服装", "食品", "服装", "电子", "食品"],
        "数量": [1, 2, 1, 1, 3],
    })


class TestDataQuery:
    """数据查询工具测试"""

    def test_filter_by_column(self, sample_df):
        from app.agent.tools.data_query import _filter_data
        result = _filter_data(sample_df, "品类", "服装")
        assert len(result) == 2

    def test_filter_by_numeric(self, sample_df):
        from app.agent.tools.data_query import _filter_data
        result = _filter_data(sample_df, "金额", "100", ">")
        assert len(result) == 3  # 200, 150, 300 均 > 100

    def test_group_data(self, sample_df):
        from app.agent.tools.data_query import _group_data
        result = _group_data(sample_df, "品类", "金额", "sum")
        assert len(result) == 3
        # 按金额排序
        result_sorted = result.sort_values("金额", ascending=False)
        assert result_sorted.iloc[0]["品类"] == "电子"

    def test_sort_data(self, sample_df):
        from app.agent.tools.data_query import _sort_data
        result = _sort_data(sample_df, "金额", "desc")
        assert result.iloc[0]["金额"] == 300.0

    def test_find_column_exact(self, sample_df):
        from app.agent.tools.data_query import _find_column
        assert _find_column(sample_df, "订单号") == "订单号"

    def test_find_column_fuzzy(self, sample_df):
        from app.agent.tools.data_query import _find_column
        assert _find_column(sample_df, "品类") == "品类"
        # "下单" 应通过模糊匹配找到 "下单日期"
        assert _find_column(sample_df, "下单") == "下单日期"
        # 完全不相关的列应返回 None
        assert _find_column(sample_df, "不存在列") is None


class TestStatistics:
    """统计分析工具测试"""

    def test_aggregate_sum(self, sample_df):
        from app.agent.tools.statistics import _aggregate
        result = _aggregate(sample_df, "金额", "sum", None)
        assert result["type"] == "scalar"
        assert result["column"] == "金额"
        assert result["value"] == 800.0

    def test_aggregate_mean(self, sample_df):
        from app.agent.tools.statistics import _aggregate
        result = _aggregate(sample_df, "金额", "mean", None)
        assert result["value"] == 160.0

    def test_aggregate_grouped(self, sample_df):
        from app.agent.tools.statistics import _aggregate
        result = _aggregate(sample_df, "金额", "sum", "品类")
        assert result["type"] == "grouped_aggregate"
        assert result["group_column"] == "品类"

    def test_top_n(self, sample_df):
        from app.agent.tools.statistics import _top_n
        result = _top_n(sample_df, "金额", 2, "desc")
        assert len(result["data"]) == 2
        assert result["data"][0]["金额"] == 300.0


class TestVisualization:
    """图表生成工具测试"""

    def test_bar_chart(self, sample_df):
        from app.agent.tools.visualization import _build_xy_chart
        option = _build_xy_chart(sample_df, "bar", "品类", "金额", "品类销售额")
        assert "title" in option
        assert "xAxis" in option
        assert "yAxis" in option
        assert len(option["series"]) == 1
        assert option["series"][0]["type"] == "bar"

    def test_line_chart(self, sample_df):
        from app.agent.tools.visualization import _build_xy_chart
        option = _build_xy_chart(sample_df, "line", None, None, "趋势图")
        assert option["series"][0]["type"] == "line"
        assert option["series"][0]["smooth"] is True

    def test_pie_chart(self, sample_df):
        from app.agent.tools.visualization import _build_pie_chart
        option = _build_pie_chart(sample_df, "品类", "金额", "品类占比")
        assert option["series"][0]["type"] == "pie"
        assert "data" in option["series"][0]
        assert len(option["series"][0]["data"]) == 5, f"饼图数据应为5项（原始行数），实际{len(option['series'][0]['data'])}项"
