"""
@brief LangGraph 状态图组装与运行入口

将六个节点（Planner → Executor → Reflection → HumanCheck → Responder）
组装为状态图，定义条件边路由逻辑，暴露流式运行接口。
支持 Human-in-the-Loop：通过 interrupt_before 在 human_check 节点前暂停，
外部系统注入 human_approval_result 后恢复执行。
"""

import json
import os
import traceback
import logging
import asyncio
import copy
from typing import AsyncIterator, Dict, Any
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)

from app.agent.state import AgentState, create_initial_state
from app.agent.nodes.planner import planner_node
from app.agent.nodes.executor import executor_node
from app.agent.nodes.reflector import reflector_node
from app.agent.nodes.human_check import human_check_node
from app.agent.nodes.responder import responder_node


def _should_continue_after_reflection(state: AgentState) -> str:
    """
    @brief Reflection 后的路由决策
    @return "execute" 继续执行 / "respond" 生成回答 / "human_check" 人工干预
    """
    if state.get("need_human_approval"):
        return "human_check"

    plan = state.get("plan", [])
    current_idx = state.get("current_step_index", 0)

    if current_idx >= len(plan):
        return "respond"

    return "execute"


def _should_continue_after_human(state: AgentState) -> str:
    """
    @brief Human Checkpoint 后的路由决策
    @return "execute" 重新执行 / "respond" 生成回答
    """
    approval = state.get("human_approval_result")
    if approval == "approved":
        plan = state.get("plan", [])
        current_idx = state.get("current_step_index", 0)
        if current_idx < len(plan):
            return "execute"
        return "respond"
    return "respond"


def build_graph(tools: list[BaseTool]) -> StateGraph:
    """
    @brief 构建 LangGraph 状态图
    @param tools 可用工具列表
    @return 编译后的 StateGraph
    """
    workflow = StateGraph(AgentState)

    # 注册节点
    workflow.add_node("planner", planner_node)

    async def exec_node(state: AgentState) -> AgentState:
        return await executor_node(state, tools)

    workflow.add_node("executor", exec_node)
    workflow.add_node("reflector", reflector_node)
    workflow.add_node("human_check", human_check_node)
    workflow.add_node("responder", responder_node)

    # 设置入口
    workflow.set_entry_point("planner")

    # 规划完成后进入执行
    workflow.add_edge("planner", "executor")

    # 执行完成后进入反思
    workflow.add_edge("executor", "reflector")

    # 反思后条件路由
    workflow.add_conditional_edges(
        "reflector",
        _should_continue_after_reflection,
        {
            "execute": "executor",
            "respond": "responder",
            "human_check": "human_check",
        },
    )

    # 人工干预后条件路由
    workflow.add_conditional_edges(
        "human_check",
        _should_continue_after_human,
        {
            "execute": "executor",
            "respond": "responder",
        },
    )

    # 响应节点后结束
    workflow.add_edge("responder", END)

    # 编译（使用内存检查点，在 human_check 之前暂停等待外部审批）
    memory = MemorySaver()
    compiled = workflow.compile(
        checkpointer=memory,
        interrupt_before=["human_check"],
    )

    return compiled


async def run_agent(
    question: str,
    data_source_id: str,
    tools: list[BaseTool],
    data_summary: str = "",
    graph: StateGraph | None = None,
    config: dict | None = None,
    resume_mode: bool = False,
    context_memory: list | None = None,
    active_data_source_id: str | None = None,
    join_data_source_ids: list[str] | None = None,  # 关联数据源 ID 列表（多选时传入）
) -> AsyncIterator[Dict[str, Any]]:
    """
    @brief 流式运行 Agent 状态图

    支持两个模式：
    1. 初始模式（resume_mode=False）：创建新状态，从 Planner 开始执行
    2. 恢复模式（resume_mode=True）：从中断点继续执行（Human Checkpoint 审批后）

    @param question 用户问题
    @param data_source_id 数据源 ID
    @param tools 可用工具列表
    @param data_summary 数据源摘要
    @param graph 已编译的状态图（可选，不传则新建）
    @param config LangGraph 配置（恢复模式必传）
    @param resume_mode 是否为恢复执行模式
    @param context_memory 上下文记忆（追问时传入）
    @param active_data_source_id 激活的数据源 ID（追问时传入）
    @yield 状态变更事件
    """
    if graph is None:
        graph = build_graph(tools)

    if config is None:
        config = {"configurable": {"thread_id": data_source_id}}

    if not resume_mode:
        initial_state = create_initial_state(
            question=question,
            data_source_id=data_source_id,
            data_summary=data_summary,
            context_memory=context_memory,
            active_data_source_id=active_data_source_id,
        )
        stream_input = initial_state
    else:
        # 恢复模式：传入 None 表示从中断点继续
        stream_input = None

    try:
        async for event in graph.astream(stream_input, config):
            for node_name, node_state in event.items():
                evt = _build_node_event(node_name, node_state, data_source_id)
                if evt:
                    yield evt

        # astream 结束后检查是否因 interrupt_before 暂停
        state_snapshot = graph.get_state(config)
        if state_snapshot and state_snapshot.next:
            next_nodes = tuple(state_snapshot.next)
            if "human_check" in next_nodes:
                state_vals = state_snapshot.values or {}
                yield {
                    "type": "human_checkpoint",
                    "check_id": f"check_{data_source_id}",
                    "action": state_vals.get("human_approval_action", "需要人工审批"),
                    "detail": _build_checkpoint_detail(state_vals),
                }
                return  # 暂停，等待外部审批后通过 resume_mode=True 恢复

        # 正常完成：获取最终状态
        final_state = graph.get_state(config)
        if final_state and final_state.values:
            f = final_state.values

            # 预生成所有格式变体（并行调用，供前端即时切换）
            format_variants = await _pre_generate_formats(f)

            yield {
                "type": "done",
                "final_response": f.get("final_response", ""),
                "charts": f.get("charts"),
                "tables": f.get("tables"),
                "format_variants": format_variants,
                "context_memory": f.get("context_memory", []),
                "anomaly_alerts": f.get("anomaly_alerts", []),
                # 携带上下文，供格式切换（reformat）复用
                "plan": [s.model_dump() for s in f.get("plan", [])],
                "tool_results": [
                    {
                        "step_id": r.step_id,
                        "success": r.success,
                        "output": _safe_serialize(r.output),
                        "error_message": r.error_message,
                    }
                    for r in f.get("tool_results", [])
                ],
                "data_summary": f.get("data_summary", ""),
                "reflection_notes": f.get("reflection_notes", []) or [],
            }
        else:
            yield {"type": "done", "final_response": "分析完成", "charts": None, "tables": None}

    except Exception as e:
        tb = traceback.format_exc()
        print(f"\n{'='*60}\n[Agent 崩溃] @ run_agent\n{tb}\n{'='*60}\n", flush=True)
        logger.error(f"Agent 执行崩溃:\n{tb}")
        try:
            import tempfile
            log_path = os.path.join(tempfile.gettempdir(), "ecommerce_agent_traceback.log")
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(tb)
        except Exception:
            pass
        yield {
            "type": "error",
            "message": f"Agent 执行异常: {type(e).__name__}: {str(e)[:300]}",
        }


def _build_node_event(node_name: str, node_state: dict, data_source_id: str) -> dict | None:
    """将节点状态转换为事件字典"""
    event = None

    if node_name == "planner":
        event = {
            "type": "planning",
            "steps": [
                {
                    "step_id": s.step_id,
                    "description": s.description,
                    "tool_name": s.tool_name,
                    "expected_output_type": s.expected_output_type,
                }
                for s in node_state.get("plan", [])
            ],
        }
    elif node_name == "executor":
        current_idx = node_state.get("current_step_index", 0)
        plan = node_state.get("plan", [])
        step_desc = ""
        if current_idx > 0 and current_idx - 1 < len(plan):
            step_desc = plan[current_idx - 1].description
        # 仅发送最近一步的工具结果（current_idx - 1 对应的步骤）
        all_results = node_state.get("tool_results", [])
        recent_results = all_results[-3:] if len(all_results) > 3 else all_results
        event = {
            "type": "step_result",
            "step_index": current_idx - 1,
            "description": step_desc,
            "results": [
                {
                    "step_id": r.step_id,
                    "success": r.success,
                    "output": r.output,
                    "error_message": r.error_message,
                }
                for r in recent_results
            ],
        }
    elif node_name == "reflector":
        event = {
            "type": "reflecting",
            "retry_count": node_state.get("retry_count", 0),
            "need_approval": node_state.get("need_human_approval", False),
            "notes": (node_state.get("reflection_notes", []) or [])[-3:],
        }
    elif node_name == "human_check":
        # 通过 interrupt_before 暂停，此节点通常不会执行到此
        event = {
            "type": "human_checkpoint",
            "check_id": f"check_{data_source_id}",
            "action": node_state.get("human_approval_action", "需要人工审批"),
            "detail": _build_checkpoint_detail(node_state),
        }
    elif node_name == "responder":
        event = {
            "type": "responding",
            "response_preview": (node_state.get("final_response", "") or "")[:200],
        }

    if event:
        return event
    return None


def _build_checkpoint_detail(state: dict) -> str:
    """构建人工审批详情文本"""
    action = state.get("human_approval_action", "")

    # 多表确认：返回候选表 JSON
    if action == "confirm_tables":
        plan = state.get("plan", [])
        idx = state.get("current_step_index", 0)
        step = plan[idx] if idx < len(plan) else None
        desc = step.description if step else "需要选择关联数据表"

        # 从 tool_results 中提取 search_data_sources 的搜索结果
        tool_results = state.get("tool_results", [])
        candidates = []
        for r in tool_results:
            if r.success and isinstance(r.output, dict) and "matches" in r.output:
                candidates = r.output["matches"]
                break

        import json
        return json.dumps({
            "action": "confirm_tables",
            "message": desc,
            "candidates": candidates,
        }, ensure_ascii=False)

    plan = state.get("plan", [])
    idx = state.get("current_step_index", 0)
    if idx < len(plan):
        step = plan[idx]
        return f"即将执行：{step.description}（使用工具：{step.tool_name}）"
    notes = state.get("reflection_notes", [])
    return notes[-1] if notes else "需要确认操作"


def _safe_serialize(obj):
    """安全序列化工具输出（处理 numpy 等非 JSON 类型，保留 dict/list 结构）"""
    import json
    try:
        return json.loads(json.dumps(obj, ensure_ascii=False, default=str))
    except Exception:
        return str(obj)[:2000]


async def _pre_generate_formats(state: dict) -> Dict[str, str]:
    """
    @brief 预生成 4 种输出格式的回答（并行调用 LLM）
    每种格式使用独立的强指令 prompt，确保输出差异显著。
    @param state 最终 AgentState（含 plan/tool_results/data_summary）
    @return {"bullet": "...", "table": "...", "report": "...", "chart": "..."}
    """
    import re
    from app.core.llm import get_llm

    # 构建数据上下文（所有格式共享）
    data_context_parts = []
    # 用户问题
    messages = state.get("messages", [])
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "human":
            data_context_parts.append(f"用户问题：{msg.content}")
            break
        elif hasattr(msg, "content"):
            data_context_parts.append(f"用户问题：{msg.content}")
            break

    # 数据源
    if state.get("data_summary"):
        data_context_parts.append(f"数据源：{state['data_summary']}")

    # 工具执行结果（摘要化，避免超长）
    plan = state.get("plan", [])
    tool_results = state.get("tool_results", [])
    for i, step in enumerate(plan):
        r = tool_results[i] if i < len(tool_results) else None
        if r and hasattr(r, 'success') and r.success:
            out = getattr(r, 'output', None)
            if out is not None:
                out_str = json.dumps(out, ensure_ascii=False, default=str) if not isinstance(out, str) else out
                data_context_parts.append(f"步骤「{step.description if hasattr(step, 'description') else step}」结果：{out_str[:2000]}")
        elif r and hasattr(r, 'success') and not r.success:
            err = getattr(r, 'error_message', '未知错误')
            data_context_parts.append(f"步骤「{step.description if hasattr(step, 'description') else step}」失败：{err}")

    data_context = "\n".join(data_context_parts)

    # ── 每格式独立强指令 ──
    FORMAT_PROMPTS = {
        "bullet": (
            "你是数据分析助手。根据下面的分析数据，用清单形式输出关键结论。\n\n"
            "【输出规则】\n"
            "1. 每行以「- 」开头\n"
            "2. 只写结论性句子，不写分析过程\n"
            "3. 绝对不要出现任何表格（不要出现 | 字符）\n"
            "4. 绝对不要出现 ## 标题\n"
            "5. 总条数 3~7 条\n"
            "6. 每条结论简短明确，不超过 40 字\n\n"
            "示例输出：\n"
            "- 总销售额为 ¥142,300，环比增长 12.5%\n"
            "- 手机配件贡献最高，占比 38%\n"
            "- 退货率 3.2%，处于健康水平\n"
        ),
        "table": (
            "你是数据分析助手。根据下面的分析数据，只输出一个 Markdown 表格。\n\n"
            "【输出规则】\n"
            "1. 主体必须是一个完整的 Markdown 表格（含表头行、分隔行、数据行）\n"
            "2. 表格前最多允许一句简短说明，表格后不要任何文字\n"
            "3. 数字保留 2 位小数，若原值已是整数则不显示小数\n"
            "4. 适当添加合计行（如总计、平均值）\n"
            "5. 列名使用中文\n\n"
            "示例输出：\n"
            "各品类销售额排名如下：\n\n"
            "| 品类 | 销售额 | 占比 |\n"
            "|------|--------|------|\n"
            "| 手机配件 | ¥54,100 | 38% |\n"
            "| 耳机 | ¥38,700 | 27% |\n"
            "| 合计 | ¥142,300 | 100% |\n"
        ),
        "report": (
            "你是资深电商数据分析师。根据下面的分析数据，撰写一份专业的数据分析报告。\n\n"
            "【报告结构——必须包含以下3个章节，缺一不可】\n"
            "## 一、核心指标概览\n"
            "用 3~5 句话概述关键数据，给出整体判断（如「本月表现优于上月」「核心品类增长强劲」）。\n\n"
            "## 二、细分维度分析\n"
            "按品类/时间/地区等维度展开分析，每个维度用一段文字叙述（不是清单），\n"
            "说明数据背后的业务含义。可以嵌入1~2个表格佐证，但每段必须有文字解读。\n\n"
            "## 三、行动建议\n"
            "基于以上分析，给出3条具体的、可执行的经营建议。\n"
            "每条建议包含「问题/机会」+「建议动作」+「预期效果」。\n\n"
            "【风格要求】\n"
            "1. 用自然段落叙述，不要用「- 」开头的清单格式\n"
            "2. 数据分析为主，语气专业但不过于技术化\n"
            "3. 数字要加单位或解释（如「¥14.2万」而非「142000」）\n"
            "4. 总字数 300~500 字\n\n"
            "示例输出：\n"
            "## 一、核心指标概览\n"
            "本月总销售额达 ¥14.2 万，环比增长 12.5%，表现超出预期。手机配件品类贡献了 38% 的销售额，是最核心的营收来源。\n\n"
            "## 二、细分维度分析\n"
            "手机配件本月销售额 ¥5.4 万，同比增长 22%，主要受新品上市的拉动……\n\n"
            "## 三、行动建议\n"
            "1. 加大手机配件促销力度。该品类贡献最高但增速趋缓，建议本周推出满减活动，预计可提升 10% 转化率……\n"
        ),
        "chart": (
            "你是数据分析助手。根据下面的分析数据，用 1~3 句简短文字点出图表中的关键发现。\n\n"
            "【输出规则】\n"
            "1. 只输出 1~3 句简短话\n"
            "2. 绝对不要出现任何表格（不要出现 | 字符）\n"
            "3. 绝对不要出现 ## 标题\n"
            "4. 每句话不超过 30 字\n"
            "5. 聚焦在「整体趋势」「最高/最低值」「异常点」上\n\n"
            "示例输出：\n"
            "7 月 GMV 达到峰值 ¥18,200，超出月均 30%。8 月回落至正常水平。手机配件持续领跑，贡献总销售额的 38%。\n"
        ),
    }

    def _strip_tables(text: str) -> str:
        text = re.sub(r'(?m)^[ \t]*\|.*\|[ \t]*$', '', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    async def gen_one(fmt: str) -> tuple[str, str]:
        try:
            llm = get_llm()
            prompt = FORMAT_PROMPTS[fmt]
            response = await llm.chat([
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"分析数据如下：\n\n{data_context}\n\n请严格按规则输出。不要输出任何规则说明或前缀。"},
            ])
            clean = (response or "").strip()
            # 要点/图表格式确定性清洗表格残留
            if fmt in ("bullet", "chart"):
                clean = _strip_tables(clean)
            return fmt, clean
        except Exception:
            return fmt, ""

    results = await asyncio.gather(*[gen_one(f) for f in ["bullet", "table", "report", "chart"]])

    # 去重：丢弃与主回答完全相同或为空的变体
    primary_response = (state.get("final_response") or "").strip()
    variants = {}
    for fmt, resp in results:
        if not resp or not resp.strip():
            continue
        if primary_response and resp.strip()[:100] == primary_response[:100]:
            continue
        variants[fmt] = resp

    return variants if len(variants) >= 1 else {}
