"""
@brief 对话 API 模块

- WebSocket /ws/chat：流式对话，Human Checkpoint 审批
- REST GET/DELETE /api/sessions：历史会话管理
"""

import json
import uuid
import traceback
from typing import Dict, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from app.agent.graph import run_agent
from app.agent.tools.schema import get_all_tools
from app.core.database import SessionLocal
from app.models.analysis_record import AnalysisRecord
from app.models.data_source import DataSource

router = APIRouter()


# ─────────────────────────────────────────────
# WebSocket /ws/chat
# ─────────────────────────────────────────────

@router.websocket("/ws/chat")
async def chat_websocket(websocket: WebSocket):
    """
    @brief WebSocket 对话端点

    消息协议：
    - 客户端 → 服务端:
      {"type": "chat", "content": "问题", "data_source_id": "xxx"}
      {"type": "human_approval", "check_id": "xxx", "result": "approved"|"rejected"}

    - 服务端 → 客户端:
      {"type": "planning", "steps": [...]}
      {"type": "step_result", "step_index": N, "description": "...", "results": [...]}
      {"type": "reflecting", "retry_count": N, "need_approval": bool, "notes": [...]}
      {"type": "human_checkpoint", "check_id": "...", "action": "...", "detail": "..."}
      {"type": "responding", "response_preview": "..."}
      {"type": "done", "final_response": "...", "charts": [...], "tables": [...]}
      {"type": "error", "message": "..."}
    """
    await websocket.accept()
    session_id = str(uuid.uuid4())
    # current_state 存储 graph 实例和 config，用于 Human Checkpoint 恢复
    current_state: Dict[str, Any] = {
        "graph": None, "config": None, "check_id": None, "data_source_id": None,
        "last_ctx": None,  # 上一轮分析上下文，供格式切换（reformat）复用
        "context_memory": [],  # 多轮对话上下文记忆
    }

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "消息格式无效，请发送 JSON"})
                continue

            msg_type = msg.get("type", "")

            # ── 处理聊天消息 ──
            if msg_type == "chat":
                question = msg.get("content", "")
                data_source_id = msg.get("data_source_id", "")
                join_data_source_ids: list[str] = msg.get("join_data_source_ids", []) or []

                # data_source_id 省略时自动沿用上次激活的数据源
                if not data_source_id:
                    data_source_id = current_state.get("data_source_id", "")
                if not question or not data_source_id:
                    await websocket.send_json({"type": "error", "message": "缺少 content 或 data_source_id"})
                    continue

                # 检测数据源是否切换，切换时清空上下文记忆
                prev_ds = current_state.get("data_source_id", "")
                context_memory = current_state.pop("context_memory", None)
                if prev_ds and data_source_id != prev_ds:
                    context_memory = None  # 切换数据源，上下文不可串联

                # ── 格式切换请求：复用上一轮分析上下文，不重新规划 ──
                reformat = msg.get("reformat")
                if reformat and current_state.get("last_ctx"):
                    await _handle_reformat(websocket, session_id, current_state, reformat)
                    continue

                # 持久化用户原始消息
                _save_record(
                    session_id=session_id,
                    event_type="chat",
                    event={"content": question, "data_source_id": data_source_id},
                    role_override="user",
                )

                # 获取数据源摘要（含关联数据源信息）
                data_summary = _get_data_summary(data_source_id, join_data_source_ids)

                # 获取工具
                tools = get_all_tools()

                # 构建或复用 Graph 实例（thread_id 使用唯一 session_id 隔离多连接）
                if current_state["graph"] is None:
                    from app.agent.graph import build_graph
                    current_state["graph"] = build_graph(tools)
                    current_state["config"] = {"configurable": {"thread_id": session_id}}

                current_state["data_source_id"] = data_source_id

                try:
                    # 流式运行 Agent
                    async for event in run_agent(
                        question=question,
                        data_source_id=data_source_id,
                        tools=tools,
                        data_summary=data_summary or "",
                        graph=current_state["graph"],
                        config=current_state["config"],
                        resume_mode=False,
                        context_memory=context_memory,
                        active_data_source_id=data_source_id,
                        join_data_source_ids=join_data_source_ids,
                    ):
                        event_type = event.get("type", "")

                        # 持久化消息
                        _save_record(session_id, event_type, event)

                        await websocket.send_json(event)

                        # 缓存分析上下文，供格式切换复用
                        if event_type == "done":
                            current_state["last_ctx"] = {
                                "question": question,
                                "data_summary": event.get("data_summary") or data_summary or "",
                                "plan": event.get("plan") or [],
                                "tool_results": event.get("tool_results") or [],
                                "reflection_notes": event.get("reflection_notes") or [],
                            }
                            # 缓存上下文记忆，供下一轮追问使用（从 event 中获取或从 state 提取）
                            if event.get("context_memory") is not None:
                                current_state["context_memory"] = event["context_memory"]

                        # 如果是 human_checkpoint，Agent 已在 graph 层面暂停
                        if event_type == "human_checkpoint":
                            current_state["check_id"] = event.get("check_id", "")

                except Exception as e:
                    error_msg = f"Agent 执行异常: {str(e)}"
                    await websocket.send_json({"type": "error", "message": error_msg})
                    _save_record(session_id, "error", {"message": error_msg})

            # ── 处理人工审批 ──
            elif msg_type == "human_approval":
                result = msg.get("result", "rejected")
                check_id = msg.get("check_id", "")
                selected_table_ids = msg.get("selected_table_ids", [])

                if result not in ("approved", "rejected"):
                    await websocket.send_json({"type": "error", "message": "result 必须是 approved 或 rejected"})
                    continue

                graph = current_state["graph"]
                config = current_state["config"]
                if graph is None or config is None:
                    await websocket.send_json({"type": "error", "message": "没有等待审批的操作"})
                    continue

                # 向 Graph 状态注入审批结果和选中的表
                approval_update = {"human_approval_result": result}
                if selected_table_ids:
                    approval_update["approved_table_ids"] = selected_table_ids
                graph.update_state(config, approval_update)

                # 从 Human Checkpoint 中断点恢复执行
                data_source_id = current_state.get("data_source_id")
                if not data_source_id:
                    await websocket.send_json({"type": "error", "message": "无法恢复：数据源信息丢失"})
                    continue
                tools = get_all_tools()

                await websocket.send_json({
                    "type": "approval_processed",
                    "check_id": check_id,
                    "result": result,
                })
                _save_record(session_id, "human_approval", {"check_id": check_id, "result": result})

                try:
                    async for event in run_agent(
                        question="",  # 恢复模式无需 question
                        data_source_id=str(data_source_id),
                        tools=tools,
                        graph=graph,
                        config=config,
                        resume_mode=True,
                    ):
                        event_type = event.get("type", "")
                        _save_record(session_id, event_type, event)
                        await websocket.send_json(event)
                except Exception as e:
                    error_msg = f"恢复执行异常: {str(e)}"
                    await websocket.send_json({"type": "error", "message": error_msg})
                    _save_record(session_id, "error", {"message": error_msg})

            else:
                await websocket.send_json({"type": "error", "message": f"未知消息类型: {msg_type}"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": f"服务异常: {str(e)}"})
        except Exception:
            pass


# ─────────────────────────────────────────────
# 历史会话 API
# ─────────────────────────────────────────────

@router.get("/api/sessions")
async def list_sessions():
    """
    @brief 获取所有对话会话列表
    @return [{"session_id": str, "title": str, "message_count": int, "created_at": str}, ...]
    """
    db = SessionLocal()
    try:
        from sqlalchemy import func
        sessions = (
            db.query(
                AnalysisRecord.session_id,
                func.min(AnalysisRecord.created_at).label("created_at"),
                func.count(AnalysisRecord.id).label("message_count"),
            )
            .group_by(AnalysisRecord.session_id)
            .order_by(func.min(AnalysisRecord.created_at).desc())
            .all()
        )

        result = []
        for s in sessions:
            # 取第一条用户消息作为标题
            first = (
                db.query(AnalysisRecord)
                .filter(
                    AnalysisRecord.session_id == s.session_id,
                    AnalysisRecord.role == "user",
                )
                .order_by(AnalysisRecord.created_at.asc())
                .first()
            )
            title = "新对话"
            if first:
                try:
                    content = json.loads(first.content) if isinstance(first.content, str) else first.content
                    title = str(content.get("question", content.get("content", "新对话")))[:50]
                except (json.JSONDecodeError, TypeError):
                    title = str(first.content)[:50]

            result.append({
                "session_id": s.session_id,
                "title": title,
                "message_count": s.message_count,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            })

        return result
    finally:
        db.close()


@router.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """
    @brief 获取会话的全部消息
    @param session_id 会话 ID
    @return [{"id": str, "role": str, "content": str, "msg_type": str, "created_at": str}, ...]
    """
    db = SessionLocal()
    try:
        records = (
            db.query(AnalysisRecord)
            .filter(AnalysisRecord.session_id == session_id)
            .order_by(AnalysisRecord.created_at.asc())
            .all()
        )
        return [r.to_dict() for r in records]
    finally:
        db.close()


@router.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """
    @brief 删除会话及其所有消息
    @param session_id 会话 ID
    @return {"message": "删除成功"}
    """
    db = SessionLocal()
    try:
        db.query(AnalysisRecord).filter(
            AnalysisRecord.session_id == session_id
        ).delete()
        db.commit()
        return {"message": "删除成功"}
    finally:
        db.close()


@router.delete("/api/sessions/{session_id}/messages/{record_id}")
async def delete_session_message(session_id: str, record_id: str):
    """
    @brief 删除会话中的单条消息（同时删除关联的 AI 回复）
    @param session_id 会话 ID
    @param record_id 消息记录 ID
    """
    db = SessionLocal()
    try:
        target = db.query(AnalysisRecord).filter(
            AnalysisRecord.id == record_id,
            AnalysisRecord.session_id == session_id,
        ).first()

        if target is None:
            raise HTTPException(status_code=404, detail="消息记录不存在")

        # 如果删除的是用户消息，同时删除紧随其后的 AI 回复（包含图表表格）
        db.delete(target)
        db.commit()
        return {"deleted_id": record_id}
    finally:
        db.close()


# ─────────────────────────────────────────────
# 辅助函数
# ─────────────────────────────────────────────

async def _handle_reformat(websocket: WebSocket, session_id: str, current_state: Dict[str, Any], fmt: str):
    """
    @brief 处理格式切换请求：复用上一轮分析上下文，预生成全部格式变体
    @param websocket WebSocket 连接
    @param session_id 会话 ID
    @param current_state 连接级状态（含 last_ctx 缓存）
    @param fmt 目标格式: table / report / bullet / chart
    """
    import asyncio as aio
    import copy
    import re
    from langchain_core.messages import HumanMessage
    from app.agent.state import AgentState, AnalysisStep, ToolResult
    from app.agent.nodes.responder import responder_node

    ctx = current_state["last_ctx"]
    fmt_label = {
        "table": "表格",
        "report": "分段报告",
        "bullet": "要点",
        "chart": "图表",
    }.get(fmt, "要点")

    plan = [AnalysisStep(**s) for s in ctx.get("plan", [])]
    tool_results = [ToolResult(**r) for r in ctx.get("tool_results", [])]

    if not plan:
        await websocket.send_json({
            "type": "error",
            "message": "没有可用的分析结果，请先提出一个分析问题",
        })
        return

    def build_state():
        return AgentState(
            messages=[HumanMessage(content=f"请将关于「{ctx.get('question', '该分析')}」的结果以{fmt_label}形式重新输出")],
            data_source_id=current_state.get("data_source_id"),
            data_summary=ctx.get("data_summary", ""),
            plan=plan,
            current_step_index=len(plan),
            tool_results=tool_results,
            reflection_notes=ctx.get("reflection_notes", []),
            context_memory=current_state.get("context_memory", []),
            retry_count=0,
            need_human_approval=False,
            final_response=None,
            charts=None,
            tables=None,
        )

    await websocket.send_json({
        "type": "reflecting",
        "retry_count": 0,
        "need_approval": False,
        "notes": [f"正在以{fmt_label}格式重新组织结果..."],
    })

    # 并行生成全部 4 种格式
    all_formats = ["bullet", "table", "report", "chart"]

    async def gen_one(f: str) -> tuple[str, str]:
        try:
            s = build_state()
            new_state = await responder_node(s, format_override=f)
            raw = new_state.get("final_response", "") if new_state else ""
            clean = re.sub(r'\n?\s*\[FORMAT:\w+\]\s*$', '', raw).rstrip()
            return f, clean
        except Exception as e:
            return f, f"格式化失败: {str(e)[:100]}"

    results = await aio.gather(*[gen_one(f) for f in all_formats])
    format_variants = {f: resp for f, resp in results if resp}

    # 以用户请求的格式作为主回答
    final_response = format_variants.get(fmt, "")

    # 获取图表/表格数据（从 tool_results 提取）
    charts, tables = _extract_charts_tables_from_results(tool_results)

    event = {
        "type": "done",
        "final_response": final_response,
        "format_variants": format_variants,
        "charts": charts,
        "tables": tables,
    }
    _save_record(session_id, "done", event)
    await websocket.send_json(event)


def _get_data_summary(data_source_id: str, join_data_source_ids: list[str] | None = None) -> str:
    """获取数据源摘要描述（含示例数据和关联数据源信息）"""
    db = SessionLocal()
    try:
        summaries = [_build_single_summary(db, data_source_id, is_primary=True)]

        # 添加关联数据源摘要
        if join_data_source_ids:
            for jid in join_data_source_ids:
                s = _build_single_summary(db, jid, is_primary=False)
                if s:
                    summaries.append(f"\n[关联数据源 - 可 JOIN 使用]:\n{s}")

        return "\n".join(summaries)
    finally:
        db.close()


def _build_single_summary(db, source_id: str, is_primary: bool = True) -> str:
    """构建单个数据源的摘要"""
    source = db.query(DataSource).filter(DataSource.id == source_id).first()
    if source is None:
        return f"数据源 {source_id[:8]} 不可用"

    cols = source.columns_meta or []
    col_desc = ", ".join([f"{c.get('name', '?')}({c.get('dtype', '?')})" for c in cols])

    # 标注列角色
    geo_keywords = ["城市", "省份", "地区", "地址", "city", "province", "region", "省", "市", "区"]
    time_keywords = ["日期", "时间", "date", "time", "下单", "创建"]
    id_keywords = ["编号", "ID", "id", "编码", "code"]
    col_tags = []
    for c in cols:
        name = str(c.get("name", ""))
        tags = []
        if any(kw in name for kw in geo_keywords):
            tags.append("地理列")
        if any(kw in name for kw in time_keywords):
            tags.append("时间列")
        if any(kw in name for kw in id_keywords) and c.get("dtype", "").startswith("int"):
            tags.append("标识符列")
        if tags:
            col_tags.append(f"{name}{{{','.join(tags)}}}")
    if col_tags:
        col_desc += "\n列角色提示: " + ", ".join(col_tags)

    prefix = "主数据源" if is_primary else "关联表"
    summary = f"{prefix}: {source.name}（表名: {source.table_name}，{source.row_count}行）\n"
    summary += f"列名及类型: {col_desc}\n"

    # 示例数据
    try:
        from app.services.data_ingestion import get_preview
        preview = get_preview(source_id, limit=2)
        if preview:
            sample_str = json.dumps(preview, ensure_ascii=False)
            if len(sample_str) > 250:
                sample_str = sample_str[:247] + "..."
            summary += f"示例: {sample_str}\n"
    except Exception:
        pass

    return summary


def _extract_charts_tables_from_results(tool_results: list):
    """从 ToolResult 列表中提取图表和表格数据"""
    charts = []
    tables = []
    for r in tool_results:
        if not r.success or r.output is None:
            continue
        output = r.output
        if isinstance(output, dict):
            if "echarts_option" in output:
                charts.append(output)
            elif "chart_type" in output:
                charts.append(output)
            elif "data" in output or "columns" in output:
                tables.append(output)
    return charts or None, tables or None


def _save_record(session_id: str, event_type: str, event: Dict[str, Any], role_override: str | None = None):
    """持久化一条对话记录"""
    db = SessionLocal()
    try:
        if role_override:
            role = role_override
        else:
            role = "assistant" if event_type != "chat" else "user"
        record = AnalysisRecord(
            session_id=session_id,
            role=role,
            content=json.dumps(event, ensure_ascii=False, default=str),
            msg_type=event_type,
        )
        db.add(record)
        db.commit()
    except Exception:
        pass
    finally:
        db.close()
