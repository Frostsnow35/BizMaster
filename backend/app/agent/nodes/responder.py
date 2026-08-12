"""
@brief Response 响应生成节点

汇总所有工具执行结果，通过 LLM 生成最终自然语言回答。
"""

import json
import re
from langchain_core.messages import AIMessage

from app.agent.state import AgentState, format_context_for_prompt, update_context_memory
from app.agent.prompts.responder_prompt import RESPONDER_SYSTEM_PROMPT
from app.agent.anomaly import detect_anomalies
from app.core.llm import get_llm

PLACEHOLDER_PATTERNS = [
    r'¥\s*XXX',
    r'XX\.?\d*%',
    r'\bxxx\b',
    r'占位',
    r'\bN/?A\b',
    r'\bTBD\b',
    r'\?{3,}',
    r'\.{4,}',
]


async def responder_node(state: AgentState, format_override: str | None = None) -> AgentState:
    """
    @brief 响应生成节点
    @param state 当前 AgentState
    @param format_override 用户指定输出格式: table / report / bullet / chart（可选）
    @return 更新后的 AgentState（final_response 已填充）
    """
    llm = get_llm()
    tool_results = state.get("tool_results", [])
    plan = state.get("plan", [])
    reflection_notes = state.get("reflection_notes", [])
    data_summary = state.get("data_summary", "")
    data_source_id = state.get("data_source_id", "")

    # 异常检测：在所有步骤执行完毕后检测关键指标偏离
    anomaly_alerts = state.get("anomaly_alerts", [])
    if not anomaly_alerts and tool_results and data_source_id:
        try:
            anomaly_alerts = detect_anomalies(tool_results, data_source_id)
            state["anomaly_alerts"] = anomaly_alerts
        except Exception:
            anomaly_alerts = []  # 异常检测失败不影响主流程

    # 构建系统提示词（用户指定格式时追加强制指令）
    system_prompt = RESPONDER_SYSTEM_PROMPT

    # 注入上下文记忆（替换 {context_memory} 占位符）
    context_memory = state.get("context_memory", [])
    ctx_text = format_context_for_prompt(context_memory)
    system_prompt = system_prompt.replace("{context_memory}", ctx_text if ctx_text else "（无，这是新对话的第一轮）")

    if format_override:
        fmt_label = {
            "table": "表格",
            "report": "分段报告",
            "bullet": "要点",
            "chart": "图表",
        }.get(format_override, "要点")
        system_prompt += (
            f"\n\n## 用户指定格式\n"
            f"用户明确要求以「{fmt_label}」形式输出。本次回答必须完全遵循该格式，"
            f"并在回答末尾嵌入 [FORMAT:{format_override}] 标记。"
        )

    # 统计成败
    success_count = sum(1 for r in tool_results if r.success)
    fail_count = len(tool_results) - success_count

    # 构建上下文摘要
    context_parts = []

    # 原始问题
    if state["messages"]:
        user_msg = state["messages"][-1]
        context_parts.append(f"用户问题：{user_msg.content}")

    # 数据源信息（帮助诊断失败原因）
    if data_summary:
        context_parts.append(f"\n数据源信息：{data_summary}")

    # 执行步骤与结果（只保留关键信息）
    context_parts.append(f"\n执行结果：{success_count}成功 / {fail_count}失败（共{len(plan)}步）")

    for i, step in enumerate(plan):
        step_result = tool_results[i] if i < len(tool_results) else None
        if step_result and step_result.success and step_result.output is not None:
            output_str = _serialize_output(step_result.output)
            context_parts.append(f"\n步骤{step.step_id}: {step.description} → 成功，{output_str}")
        elif step_result and not step_result.success:
            context_parts.append(f"\n步骤{step.step_id}: {step.description} → 失败：{step_result.error_message}")

    # 反思记录（仅失败相关）
    if reflection_notes:
        fail_notes = [n for n in reflection_notes if "失败" in n or "错误" in n or "异常" in n]
        if fail_notes:
            context_parts.append("\n诊断记录：")
            for note in fail_notes[-3:]:
                context_parts.append(f"- {note}")

    # 异常检测标签
    if anomaly_alerts:
        context_parts.append("\n异常检测提醒（请在回答中主动标注以下异常）：")
        for alert in anomaly_alerts:
            direction = alert.get("direction", "变化")
            context_parts.append(
                f"- ⚠️ {alert['metric']}：当前 {alert['current']}，"
                f"历史均值 {alert['avg']}，{direction} {abs(alert['change_pct']):.1f}%"
                f"（严重程度：{alert['severity']}）"
                f" 可能原因：{', '.join(alert.get('possible_causes', []))}"
            )

    context = "\n".join(context_parts)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": context},
    ]

    try:
        response = await llm.chat(messages)
        # 占位符检测
        _placeholder_detected = False
        if response:
            for pattern in PLACEHOLDER_PATTERNS:
                if re.search(pattern, response, re.IGNORECASE):
                    _placeholder_detected = True
                    break
        if _placeholder_detected:
            state["final_response"] = _build_fallback_response(state)
            state.setdefault("reflection_notes", []).append("响应含占位符，已降级为兜底回答")
        else:
            state["final_response"] = response
    except Exception as e:
        fallback = _build_fallback_response(state)
        state["final_response"] = fallback

    # 提取图表和表格数据
    charts, tables = _extract_charts_tables(tool_results)
    if charts:
        state["charts"] = charts
    if tables:
        state["tables"] = tables

    # 添加 AI 消息到对话历史
    ai_msg = AIMessage(content=state["final_response"])
    state["messages"].append(ai_msg)

    # 更新上下文记忆（从本轮回答中提取关键指标，供下一轮追问使用）
    update_context_memory(state)

    return state


def _serialize_output(output) -> str:
    """序列化工具输出为可读字符串"""
    if isinstance(output, str):
        return output[:1000]
    elif isinstance(output, dict):
        # 如果含 echarts option，标记为图表
        if "echarts_option" in output or "chart_type" in output:
            return "[图表数据]"
        return json.dumps(output, ensure_ascii=False, default=str)[:1000]
    elif isinstance(output, list):
        if len(output) > 10:
            summary = json.dumps(output[:3], ensure_ascii=False, default=str)
            return f"{summary} ... (共 {len(output)} 条)"
        return json.dumps(output, ensure_ascii=False, default=str)[:1000]
    else:
        return str(output)[:500]


def _extract_charts_tables(tool_results: list):
    """从工具结果中提取图表和表格数据"""
    charts = []
    tables = []
    for result in tool_results:
        if not result.success or result.output is None:
            continue
        output = result.output
        if isinstance(output, dict):
            if "echarts_option" in output:
                charts.append(output)
            elif "chart_type" in output:
                charts.append(output)
            elif "data" in output or "columns" in output:
                tables.append(output)
    return charts or None, tables or None


def _build_fallback_response(state: AgentState) -> str:
    """构建兜底回答（LLM 不可用时）"""
    tool_results = state.get("tool_results", [])
    plan = state.get("plan", [])
    data_summary = state.get("data_summary", "")

    success_count = sum(1 for r in tool_results if r.success)
    total_count = len(plan)

    if success_count == 0 and total_count > 0:
        last_error = tool_results[-1].error_message if tool_results else "未知错误"
        # 数据源不匹配时给出具体建议
        if "数据源不匹配" in str(last_error):
            return f"{last_error}"
        return f"分析无法完成：{last_error}。数据源结构：{data_summary}。请检查后重试。"

    if total_count == 0:
        return "未能生成分析计划，请尝试更具体地描述您的分析需求。"

    parts = [f"分析完成，共执行 {total_count} 个步骤，其中 {success_count} 个成功。"]

    for r in tool_results:
        if r.success and r.output is not None:
            output_str = str(r.output)
            if len(output_str) > 300:
                output_str = output_str[:300] + "..."
            parts.append(f"结果 ({r.step_id}): {output_str}")

    return "\n".join(parts)
