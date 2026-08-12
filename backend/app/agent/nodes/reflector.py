"""
@brief Reflection 反思节点

校验工具执行结果质量，控制重试与人工干预触发。
"""

import json
import re
from app.agent.state import AgentState
from app.agent.prompts.reflector_prompt import REFLECTOR_SYSTEM_PROMPT
from app.core.llm import get_llm
from app.core.config import config


async def reflector_node(state: AgentState) -> AgentState:
    """
    @brief 反思校验节点
    @param state 当前 AgentState
    @return 更新后的 AgentState（可能设置 retry_count 或 need_human_approval）
    """
    tool_results = state.get("tool_results", [])
    plan = state.get("plan", [])
    current_idx = state.get("current_step_index", 0)
    max_retry = config.analysis.max_retry_count

    if not tool_results:
        return state

    # 获取最近一次工具执行结果
    last_result = tool_results[-1]
    current_step = plan[current_idx] if current_idx < len(plan) else None

    # 特殊步骤：请求用户确认使用哪些表
    if current_step and current_step.tool_name == "@human_confirm_tables":
        state["need_human_approval"] = True
        state["human_approval_action"] = "confirm_tables"
        state["retry_count"] = 0
        state["current_step_index"] = current_idx + 1  # 推进索引，审批后直接进入下一步
        state.setdefault("reflection_notes", []).append(
            "请求用户确认关联表选择"
        )
        return state

    # search_data_sources 执行后：检查是否需要请求用户确认
    if current_step and current_step.tool_name == "search_data_sources" and last_result.success:
        matches = (last_result.output or {}).get("matches", []) if isinstance(last_result.output, dict) else []
        if matches:
            # 有匹配结果：直接标记为需要用户确认（下一轮 planner 会生成 @human_confirm_tables）
            state["retry_count"] = 0
            state["current_step_index"] = current_idx + 1
            state.setdefault("reflection_notes", []).append(
                f"找到 {len(matches)} 个候选表: {[m.get('name','') for m in matches[:5]]}"
            )
            return state

    # 数据源不匹配：直接跳到responder，不重试
    if "数据源不匹配" in (last_result.error_message or "") or \
       (current_step and not current_step.tool_name):
        state["retry_count"] = 0
        state["current_step_index"] = current_idx + 1
        state.setdefault("reflection_notes", []).append(
            f"数据源不匹配，跳过重试: {last_result.error_message}"
        )
        state["need_skip_retry"] = True
        return state

    # 快速判断：如果执行成功且输出不为空，大概率合格
    if last_result.success and last_result.output is not None:
        # 对于简单场景直接通过，跳过 LLM 调用
        if _quick_validate(last_result, current_step):
            state["retry_count"] = 0
            state["current_step_index"] = current_idx + 1
            state.setdefault("reflection_notes", []).append(
                f"步骤 {last_result.step_id} 校验通过"
            )
            return state

    # 需要 LLM 深度判断
    llm = get_llm()
    step_desc = current_step.description if current_step else "未知步骤"
    result_summary = _format_result_summary(last_result)

    messages = [
        {"role": "system", "content": REFLECTOR_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"上一步任务：{step_desc}\n执行结果：\n{result_summary}\n\n请判断结果是否合格。",
        },
    ]

    try:
        response = await llm.chat(messages)
        parsed = _parse_reflection(response)

        if parsed.get("is_valid", True):
            # 合格：重置重试计数，移到下一步
            state["retry_count"] = 0
            state["current_step_index"] = current_idx + 1
            state.setdefault("reflection_notes", []).append(
                f"步骤 {last_result.step_id} 校验通过: {parsed.get('reason', '')}"
            )
        else:
            # 不合格：增加重试计数
            state["retry_count"] = state.get("retry_count", 0) + 1
            retry_count = state["retry_count"]
            reason = parsed.get("reason", "结果无效")
            hint = parsed.get("correction_hint", "")

            if retry_count >= max_retry:
                # 重试耗尽，跳过该步骤继续执行后续
                state["retry_count"] = 0
                state["current_step_index"] = current_idx + 1
                state.setdefault("reflection_notes", []).append(
                    f"步骤 {last_result.step_id} 重试 {retry_count} 次后仍失败: {reason}。提示: {hint}。已跳过该步骤。"
                )
            else:
                # 修正参数后重试
                if hint and current_step:
                    # 将修正提示注入到下一步的工具参数中
                    current_step.tool_args["_correction_hint"] = hint
                state.setdefault("reflection_notes", []).append(
                    f"步骤 {last_result.step_id} 校验不通过（第 {retry_count}/{max_retry} 次重试）: {reason}"
                )
    except Exception:
        # LLM 调用失败时的兜底策略
        if last_result.success:
            state["retry_count"] = 0
            state["current_step_index"] = current_idx + 1
        else:
            state["need_human_approval"] = True

    return state


def _quick_validate(result, step) -> bool:
    """
    @brief 快速验证：无需 LLM 即可判断的简单场景
    @return True 表示合格可跳过 LLM 判断
    """
    if not result.success:
        return False
    if result.output is None:
        return False
    # 图表输出：有 echarts_option 或 chart_type 即视为有效
    if isinstance(result.output, dict):
        if "echarts_option" in result.output or "chart_type" in result.output:
            return True
        # 表格输出：同时有 columns 和 data
        if "columns" in result.output and "data" in result.output:
            data = result.output.get("data", [])
            return isinstance(data, list) and len(data) > 0
        # 标量输出：有 value 字段
        if "value" in result.output:
            return result.output["value"] is not None
        # 描述性统计：有 statistics 字段
        if "statistics" in result.output:
            stats = result.output.get("statistics", {})
            return isinstance(stats, dict) and len(stats) > 0
        # 对比分析：有 change_rate 字段
        if "change_rate" in result.output or "current_value" in result.output:
            return True
    # 列表输出
    if isinstance(result.output, list) and len(result.output) > 0:
        return True
    return False


def _format_result_summary(result) -> str:
    """格式化工具执行结果为 LLM 可读的摘要"""
    lines = []
    if result.success:
        lines.append("执行状态: 成功")
        output = result.output
        if isinstance(output, dict):
            for k, v in output.items():
                v_str = str(v)
                if len(v_str) > 500:
                    v_str = v_str[:500] + "..."
                lines.append(f"{k}: {v_str}")
        elif isinstance(output, list):
            lines.append(f"返回 {len(output)} 条记录")
            if output:
                lines.append(f"首条数据: {str(output[0])[:300]}")
        elif isinstance(output, str):
            lines.append(f"输出: {output[:500]}")
        else:
            lines.append(f"输出类型: {type(output).__name__}")
    else:
        lines.append(f"执行状态: 失败")
        lines.append(f"错误: {result.error_message}")
    return "\n".join(lines)


def _parse_reflection(response: str) -> dict:
    """解析 LLM 反思输出"""
    json_match = re.search(r'\{[^{}]*"is_valid"\s*:\s*(true|false)[^{}]*\}', response, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass
    return {"is_valid": True, "reason": "无法解析反思结果，默认通过"}
