"""
@brief Human Checkpoint 人机干预节点

在需要人工审批的场景下暂停 Agent 执行，等待用户决策后恢复。
"""

from app.agent.state import AgentState


async def human_check_node(state: AgentState) -> AgentState:
    """
    @brief 人机干预节点：标记中断点，等待审批

    LangGraph 的 interrupt() 机制会在节点返回后暂停 Graph 执行。
    外部系统（WebSocket handler）检测到 need_human_approval=True 后，
    通过 graph.update_state() 注入 human_approval_result 来恢复执行。

    @param state 当前 AgentState
    @return 更新后的 AgentState
    """
    # 确保审批结果字段已初始化
    state.setdefault("human_approval_result", None)

    # 当前审批结果已在到达此节点前由外部注入
    # 根据审批结果决定下一步路由
    approval = state.get("human_approval_result")

    if approval == "approved":
        # 用户批准：清除重试计数和审批标记，准备重新执行
        state["retry_count"] = 0
        state["need_human_approval"] = False
        state.setdefault("reflection_notes", []).append("用户已批准，重新尝试执行")
    elif approval == "rejected":
        # 用户拒绝：跳过当前步骤，标记为失败
        state["need_human_approval"] = False
        state.setdefault("reflection_notes", []).append("用户已拒绝，跳过当前操作")
        state["current_step_index"] = state.get("current_step_index", 0) + 1
    else:
        # 等待审批中（首次进入此节点）
        state.setdefault("reflection_notes", []).append("等待用户审批...")

    return state
