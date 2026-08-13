"""
@brief Planning 规划节点

调用 LLM 将用户自然语言问题分解为有序的分析步骤。
"""

import json
import re
from typing import List
from langchain_core.messages import SystemMessage, HumanMessage

from app.agent.state import AgentState, AnalysisStep, format_context_for_prompt
from app.agent.prompts.planner_prompt import PLANNER_SYSTEM_PROMPT
from app.agent.roles import get_role
from app.core.llm import get_llm


def _parse_steps_from_response(response: str) -> List[AnalysisStep]:
    """
    @brief 从 LLM 回复中解析分析步骤
    @param response LLM 回复文本
    @return AnalysisStep 列表
    @throws ValueError 如果解析失败
    """
    # 提取 JSON 块
    json_match = re.search(r'\{[^{]*"steps"\s*:\s*\[.*?\]\s*\}', response, re.DOTALL)
    if json_match:
        json_str = json_match.group(0)
    else:
        json_str = response

    try:
        data = json.loads(json_str)
        steps = data.get("steps", [])
    except json.JSONDecodeError:
        raise ValueError(f"无法解析 LLM 输出的步骤计划: {response[:200]}")

    if not steps:
        raise ValueError("LLM 未输出任何分析步骤")

    result = []
    for s in steps:
        step = AnalysisStep(
            step_id=s.get("step_id", len(result) + 1),
            description=s.get("description", f"步骤 {len(result) + 1}"),
            tool_name=s.get("tool_name", "data_query"),
            tool_args=s.get("tool_args", {}),
            expected_output_type=s.get("expected_output_type", "text"),
        )
        result.append(step)

    return result


async def planner_node(state: AgentState) -> AgentState:
    """
    @brief 规划节点：将用户问题分解为分析步骤
    @param state 当前 AgentState
    @return 更新后的 AgentState（plan 字段已填充）
    """
    llm = get_llm()
    user_question = state["messages"][-1].content

    data_summary = state.get("data_summary", "暂无数据源信息")
    # 使用字符串拼接避免 .format() 将 JSON 花括号误解析为占位符
    idx = PLANNER_SYSTEM_PROMPT.find("{data_summary}")
    if idx >= 0:
        system_prompt = PLANNER_SYSTEM_PROMPT[:idx] + data_summary + PLANNER_SYSTEM_PROMPT[idx + len("{data_summary}"):]
    else:
        system_prompt = PLANNER_SYSTEM_PROMPT + "\n" + data_summary

    # 注入上下文记忆（替换 {context_memory} 占位符）
    context_memory = state.get("context_memory", [])
    ctx_text = format_context_for_prompt(context_memory)
    system_prompt = system_prompt.replace("{context_memory}", ctx_text if ctx_text else "（无，这是新对话的第一轮）")

    # 注入角色规划提示词（多角色分析引擎）
    role_key = state.get("role_key")
    role = get_role(role_key)
    if role and role.get("planner_hint"):
        system_prompt += (
            f"\n\n## 当前分析角色：{role['name']}\n"
            f"{role['planner_hint']}\n"
            f"该角色偏好的图表类型：{', '.join(role.get('chart_preferences', []))}。"
        )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"请为以下分析问题规划步骤：\n{user_question}"},
    ]

    try:
        response = await llm.chat(messages)
        plan = _parse_steps_from_response(response)
        state["plan"] = plan
        state["current_step_index"] = 0
        state["reflection_notes"] = []
        state["reflection_notes"].append(f"规划完成，共计 {len(plan)} 个步骤")
    except Exception as e:
        # 解析失败时，创建兜底单步计划（不做具体操作，返回数据概览）
        fallback_step = AnalysisStep(
            step_id=1,
            description="获取数据概览（自动规划失败，使用兜底方案）",
            tool_name="data_query",
            tool_args={"limit": 100},
            expected_output_type="table",
        )
        state["plan"] = [fallback_step]
        state["current_step_index"] = 0
        state["reflection_notes"] = [f"规划解析异常（{str(e)}），使用兜底方案"]

    return state
