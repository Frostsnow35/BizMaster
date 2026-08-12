"""
@brief Execution 执行节点

按计划步骤依次调用工具，将结果记录到状态中。
"""

import traceback
import logging
from langchain_core.tools import BaseTool

from app.agent.state import AgentState, ToolResult

logger = logging.getLogger(__name__)


async def executor_node(state: AgentState, tools: list[BaseTool]) -> AgentState:
    """
    @brief 执行当前分析步骤
    @param state 当前 AgentState
    @param tools 可用工具列表（LangChain Tool 对象）
    @return 更新后的 AgentState
    """
    plan = state.get("plan", [])
    current_idx = state.get("current_step_index", 0)

    if current_idx >= len(plan):
        state.setdefault("tool_results", []).append(
            ToolResult(
                step_id=-1,
                success=False,
                error_message="没有更多步骤可执行",
            )
        )
        return state

    current_step = plan[current_idx]

    # 数据源不匹配：Planner 判断当前数据源无法回答用户问题
    if not current_step.tool_name or current_step.tool_name.strip() == "":
        state.setdefault("tool_results", []).append(
            ToolResult(
                step_id=current_step.step_id,
                success=False,
                error_message=current_step.description or "当前数据源不匹配用户问题",
            )
        )
        state.setdefault("reflection_notes", []).append(
            f"数据源不匹配：{current_step.description}"
        )
        return state

    # 防御：确保 tool_args 是 dict
    if not isinstance(current_step.tool_args, dict):
        logger.warning(f"tool_args 类型异常: {type(current_step.tool_args)}, 重置为空字典")
        current_step.tool_args = {}

    # 查找匹配的工具
    tool = _find_tool(tools, current_step.tool_name)
    if tool is None:
        maybe_tool = _fuzzy_match_tool(tools, current_step.tool_name)
        if maybe_tool:
            state.setdefault("reflection_notes", []).append(
                f"工具 '{current_step.tool_name}' 不存在，已自动匹配为 '{maybe_tool.name}'"
            )
            tool = maybe_tool
        else:
            error_msg = f"未找到工具: {current_step.tool_name}，可用工具: {[t.name for t in tools]}"
            state.setdefault("tool_results", []).append(
                ToolResult(
                    step_id=current_step.step_id,
                    success=False,
                    error_message=error_msg,
                )
            )
            return state

    # 执行工具
    try:
        tool_input = {}
        for k, v in current_step.tool_args.items():
            tool_input[k] = v
        # 注入数据源 ID（如果工具参数未指定，且工具需要 data_source_id）
        if "data_source_id" not in tool_input and tool.name != "search_data_sources":
            tool_input["data_source_id"] = state.get("data_source_id")

        logger.info(f"执行工具 {tool.name}, 参数: {list(tool_input.keys())}")
        result = await tool.ainvoke(tool_input)
        logger.info(f"工具 {tool.name} 执行成功, 输出类型: {type(result)}")

        # 诊断：如果返回空数据，补充数据源信息
        diagnostic = _diagnose_empty_result(result, state)

        state.setdefault("tool_results", []).append(
            ToolResult(
                step_id=current_step.step_id,
                success=True,
                output=result,
            )
        )
        if diagnostic:
            state.setdefault("reflection_notes", []).append(diagnostic)
    except Exception as e:
        tb = traceback.format_exc()
        print(f"\n{'='*60}\n[Executor 错误] 工具 {tool.name}\n{tb}\n{'='*60}\n", flush=True)
        logger.error(f"工具 {tool.name} 执行失败:\n{tb}")
        # 尝试获取数据源诊断信息
        diagnostic = _diagnose_error(state)
        error_msg = f"{type(e).__name__}: {str(e)}"
        if diagnostic:
            error_msg += f"。{diagnostic}"
        state.setdefault("tool_results", []).append(
            ToolResult(
                step_id=current_step.step_id,
                success=False,
                error_message=error_msg,
            )
        )
        state.setdefault("reflection_notes", []).append(
            f"步骤 {current_step.step_id} 执行失败: {str(e)[:200]}"
        )
        if diagnostic:
            state.setdefault("reflection_notes", []).append(diagnostic)

    return state


def _diagnose_empty_result(result, state: AgentState) -> str | None:
    """诊断空结果：返回数据源的列信息和数据范围"""
    if not isinstance(result, dict):
        return None
    data = result.get("data", [])
    if data and len(data) > 0:
        return None  # 有数据，不需要诊断

    ds_id = state.get("data_source_id", "")
    ds_summary = state.get("data_summary", "")
    if ds_summary:
        return f"查询返回0条数据。数据源信息：{ds_summary}"
    return "查询返回0条数据，请检查查询条件（列名、过滤条件、日期范围）是否与数据源匹配"


def _diagnose_error(state: AgentState) -> str | None:
    """诊断错误：返回数据源结构信息帮助定位"""
    ds_summary = state.get("data_summary", "")
    if ds_summary:
        return f"数据源结构：{ds_summary}"
    return None


def _find_tool(tools: list[BaseTool], name: str) -> BaseTool | None:
    """精确匹配工具"""
    for t in tools:
        if t.name == name:
            return t
    return None


def _fuzzy_match_tool(tools: list[BaseTool], name: str) -> BaseTool | None:
    """
    @brief 模糊匹配工具名
    用于工具名拼写错误时的自动纠错。
    """
    name_lower = name.lower()
    for t in tools:
        t_lower = t.name.lower()
        if name_lower in t_lower or t_lower in name_lower:
            return t
    return None
