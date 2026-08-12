"""
@brief Agent 核心流程单元测试
"""
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestAgentState:
    """AgentState 创建测试"""

    def test_create_initial_state(self):
        from app.agent.state import create_initial_state
        state = create_initial_state("上月GMV?", "ds_12345", "数据源: orders")
        assert state["data_source_id"] == "ds_12345"
        assert state["data_summary"] == "数据源: orders"
        assert len(state["messages"]) == 1
        assert state["messages"][-1].content == "上月GMV?"
        assert state["plan"] == []
        assert state["current_step_index"] == 0
        assert state["retry_count"] == 0
        assert state["need_human_approval"] is False

    def test_analysis_step_model(self):
        from app.agent.state import AnalysisStep
        step = AnalysisStep(
            step_id=1,
            description="查询本月GMV",
            tool_name="data_query",
            tool_args={"query": "SELECT SUM(金额) FROM orders"},
            expected_output_type="number",
        )
        assert step.step_id == 1
        assert step.tool_name == "data_query"

    def test_tool_result_model(self):
        from app.agent.state import ToolResult
        r = ToolResult(step_id=1, success=True, output={"value": 100})
        assert r.success is True
        assert r.output["value"] == 100

        r2 = ToolResult(step_id=2, success=False, error_message="列不存在")
        assert r2.success is False
        assert "列不存在" in str(r2.error_message)


class TestHumanCheck:
    """Human Checkpoint 节点测试"""

    def test_approval_approved(self):
        from app.agent.state import create_initial_state
        from app.agent.nodes.human_check import human_check_node
        import asyncio

        state = create_initial_state("test", "ds_1")
        state["human_approval_result"] = "approved"
        state["need_human_approval"] = True

        result = asyncio.run(human_check_node(state))
        assert result["retry_count"] == 0
        assert result["need_human_approval"] is False

    def test_approval_rejected(self):
        from app.agent.state import create_initial_state
        from app.agent.nodes.human_check import human_check_node
        import asyncio

        state = create_initial_state("test", "ds_1")
        state["human_approval_result"] = "rejected"
        state["need_human_approval"] = True
        state["current_step_index"] = 1

        result = asyncio.run(human_check_node(state))
        assert result["current_step_index"] == 2
        assert result["need_human_approval"] is False


class TestPlanner:
    """Planner 节点测试"""

    def test_parse_steps_from_valid_json(self):
        from app.agent.nodes.planner import _parse_steps_from_response
        response = '''{"steps": [{"step_id": 1, "description": "查询GMV", "tool_name": "data_query", "tool_args": {}, "expected_output_type": "number"}]}'''
        steps = _parse_steps_from_response(response)
        assert len(steps) == 1
        assert steps[0].tool_name == "data_query"

    def test_parse_steps_from_invalid(self):
        from app.agent.nodes.planner import _parse_steps_from_response
        with pytest.raises(ValueError):
            _parse_steps_from_response("invalid response without JSON")
