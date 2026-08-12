"""
@brief Agent 状态 Schema 与数据结构定义

定义 LangGraph 状态图中使用的 AgentState 类型及分析步骤、工具结果等数据模型。
"""

from typing import TypedDict, List, Optional, Dict, Any, Annotated
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage


class AnalysisStep(BaseModel):
    """
    @brief 分析步骤模型
    Planner 节点将用户问题拆解为一系列 AnalysisStep。
    """
    step_id: int = Field(description="步骤序号（从1开始）")
    description: str = Field(description="步骤描述（面向用户展示）")
    tool_name: str = Field(description="工具名称（data_query / statistics / visualization）")
    tool_args: Dict[str, Any] = Field(default_factory=dict, description="工具参数")
    expected_output_type: str = Field(
        default="text", description="预期输出类型: table / chart / number / text"
    )


class ToolResult(BaseModel):
    """
    @brief 工具执行结果模型
    Executor 节点调用工具后，将结果封装为此模型。
    """
    step_id: int = Field(description="对应的步骤 ID")
    success: bool = Field(description="执行是否成功")
    output: Optional[Any] = Field(default=None, description="执行输出（表格/图表配置/数值/文本）")
    error_message: Optional[str] = Field(default=None, description="错误信息（失败时填充）")


class AgentState(TypedDict, total=False):
    """
    @brief Agent 全局状态

    LangGraph 状态图中流转的核心数据结构，各节点读写此状态。
    """
    # 对话相关
    messages: Annotated[List[BaseMessage], "对话历史（LangChain 消息格式）"]
    context_memory: List[Dict[str, Any]]  # 最近 5 轮分析摘要，每项含 question / data_source_name / key_findings / round

    # 数据源相关
    data_source_id: Optional[str]  # 当前分析使用的数据源 ID
    active_data_source_id: Optional[str]  # 当前对话激活的数据源 ID（追问时自动沿用）
    data_summary: Optional[str]  # 数据源概要描述（列名、类型、行数等，供 LLM 参考）

    # 规划相关
    plan: List[AnalysisStep]  # 分析步骤计划
    current_step_index: int  # 当前执行步骤索引（从 0 开始）

    # 执行相关
    tool_results: List[ToolResult]  # 工具执行结果累积列表

    # 反思相关
    reflection_notes: List[str]  # 反思纠错记录
    retry_count: int  # 当前步骤重试次数

    # 异常检测
    anomaly_alerts: List[Dict[str, Any]]  # 异常检测结果列表

    # 人类干预相关
    need_human_approval: bool  # 是否需要人工审批
    human_approval_result: Optional[str]  # 人工审批结果: "approved" / "rejected"
    human_approval_action: Optional[str]  # 审批类型: "confirm_tables" / "dangerous_operation"
    approved_table_ids: Optional[List[str]]  # 多表确认：用户批准的表 ID 列表

    # 最终输出
    final_response: Optional[str]  # 最终自然语言回答
    charts: Optional[List[Dict[str, Any]]]  # 图表配置列表（ECharts option）
    tables: Optional[List[Dict[str, Any]]]  # 表格数据列表


def create_initial_state(
    question: str,
    data_source_id: str,
    data_summary: Optional[str] = None,
    context_memory: Optional[List[Dict[str, Any]]] = None,
    active_data_source_id: Optional[str] = None,
) -> AgentState:
    """
    @brief 创建初始 AgentState
    @param question 用户问题
    @param data_source_id 数据源 ID
    @param data_summary 数据源概要（可选）
    @param context_memory 上下文记忆（可选，追问时传入）
    @param active_data_source_id 激活的数据源 ID（可选，追问时传入）
    @return 初始化的 AgentState
    """
    from langchain_core.messages import HumanMessage

    return AgentState(
        messages=[HumanMessage(content=question)],
        data_source_id=data_source_id,
        data_summary=data_summary,
        context_memory=context_memory or [],
        active_data_source_id=active_data_source_id or data_source_id,
        plan=[],
        current_step_index=0,
        tool_results=[],
        reflection_notes=[],
        retry_count=0,
        need_human_approval=False,
        human_approval_result=None,
        anomaly_alerts=[],
        final_response=None,
        charts=None,
        tables=None,
    )


# ─────────────────────────────────────────────
# 上下文记忆辅助函数
# ─────────────────────────────────────────────

def update_context_memory(state: AgentState) -> None:
    """
    @brief 从 Responder 输出中提取关键信息，追加到 context_memory，保持最近 5 条
    @param state 当前 AgentState（已含 final_response）
    """
    import re

    final_response = state.get("final_response", "")
    if not final_response:
        return

    # 提取用户问题（取最后一条 HumanMessage）
    question = ""
    messages = state.get("messages", [])
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "human":
            question = msg.content[:50] if msg.content else ""
            break

    # 提取数据源名称
    data_summary = state.get("data_summary", "")
    ds_name_match = re.search(r'数据源[：:]\s*([^\n]+)', data_summary)
    data_source_name = ds_name_match.group(1).strip() if ds_name_match else ""

    # 提取关键数值指标（匹配 ¥金额、百分比、数量等模式）
    key_findings = _extract_key_metrics(final_response)

    # 获取当前轮次
    context_memory = state.get("context_memory", [])
    if context_memory is None:
        context_memory = []
    current_round = len(context_memory) + 1

    entry = {
        "question": question or "未记录",
        "data_source_name": data_source_name,
        "key_findings": key_findings[:3],
        "round": current_round,
    }
    context_memory.append(entry)

    # 裁剪至最近 5 条
    if len(context_memory) > 5:
        context_memory = context_memory[-5:]

    state["context_memory"] = context_memory


def format_context_for_prompt(context_memory: List[Dict[str, Any]]) -> str:
    """
    @brief 将上下文记忆格式化为 Planner/Responder 可注入的文本块
    @param context_memory 上下文记忆列表
    @return 格式化的文本块，为空时返回空字符串
    """
    if not context_memory:
        return ""

    lines = ["## 上一轮分析上下文"]
    lines.append("以下是用户之前的分析记录，如果当前问题包含指代词（如「哪个」「它」「这个品类」「那个月」），请参考上下文补全。\n")

    for entry in context_memory[-3:]:  # 最多注入最近 3 轮
        r = entry.get("round", "?")
        q = entry.get("question", "")
        findings = entry.get("key_findings", [])
        if q:
            lines.append(f"第{r}轮：用户问了「{q}」")
        if findings:
            lines.append(f"  关键结论：{'；'.join(findings)}")

    return "\n".join(lines)


def _extract_key_metrics(text: str) -> List[str]:
    """
    @brief 从回答文本中提取关键数值指标
    @param text 回答文本
    @return 指标列表（如 "GMV ¥142,300"、"环比增长 12.5%"）
    """
    import re
    findings = []

    # 匹配 ¥金额 + 前后文
    money_patterns = re.findall(r'(?:销售额|GMV|营收|收入|利润|金额|客单价|消费|总额|总金额|成交额)[^\n]{0,15}?¥\s*[\d,]+(?:\.\d+)?', text)
    findings.extend(money_patterns[:3])

    # 匹配百分比（增长/下降率/占比）
    pct_patterns = re.findall(r'(?:增长|下降|减少|提升|降低|退货率|转化率|复购率|占比|贡献|比例)[^\n]{0,15}?\d+\.?\d*\s*%', text)
    findings.extend(pct_patterns[:3])

    # 匹配数量描述（含"约"、"共"等模糊前缀）
    count_patterns = re.findall(r'(?:占比|排名|贡献|商品数|订单数|客户数|品类|总销量|总数量)[^\n]{0,15}?(?:约\s*)?[\d,]+(?:\.\d+)?(?:\s*[单件个次笔])?', text)
    findings.extend(count_patterns[:2])

    # 兜底：提取回答的前 2 句作为上下文摘要（当正则匹配为空时）
    if not findings:
        sentences = re.split(r'[。；\n]', text)
        meaningful = [s.strip() for s in sentences if len(s.strip()) > 10]
        for s in meaningful[:2]:
            # 截取前 40 字
            findings.append(s[:40] + ('...' if len(s) > 40 else ''))

    # 去重并限制
    seen = set()
    unique = []
    for f in findings:
        key = f[:20]
        if key not in seen:
            seen.add(key)
            unique.append(f)

    return unique[:3]
