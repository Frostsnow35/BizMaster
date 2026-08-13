"""
@brief 专业报告生成服务

运行 Agent 分析并把结构化结果落库为 Report。
供定时调度器与手动报告接口复用。
"""

import time
import logging
from typing import Any, Dict, Optional

from app.agent.graph import run_agent
from app.agent.tools.schema import get_all_tools
from app.agent.roles import get_role, resolve_role_key
from app.api.chat import _get_data_summary
from app.core.database import SessionLocal
from app.models.report import Report

logger = logging.getLogger(__name__)


async def _collect_agent_result(question: str, data_source_id: str, role_key: str) -> Dict[str, Any]:
    """
    @brief 运行 Agent 并收集最终分析结果
    @param question 分析问题
    @param data_source_id 数据源 ID
    @param role_key 分析角色键
    @return {final_response, charts, tables, error, execution_time}
    """
    data_summary = _get_data_summary(data_source_id)
    tools = get_all_tools()

    final_response = ""
    charts = None
    tables = None
    error_msg = None
    start = time.time()

    try:
        async for event in run_agent(
            question=question,
            data_source_id=data_source_id,
            tools=tools,
            data_summary=data_summary or "",
            role_key=role_key,
        ):
            event_type = event.get("type", "")
            if event_type == "done":
                final_response = event.get("final_response", "")
                charts = event.get("charts")
                tables = event.get("tables")
            elif event_type == "error":
                error_msg = event.get("message", "分析过程出错")
    except Exception as e:
        error_msg = f"分析执行异常: {str(e)}"

    return {
        "final_response": final_response,
        "charts": charts,
        "tables": tables,
        "error": error_msg,
        "execution_time": round(time.time() - start, 2),
    }


def _build_sections(role_key: str) -> list:
    """
    @brief 按角色报告结构生成章节列表
    @param role_key 分析角色键
    @return 章节标题列表
    """
    role = get_role(resolve_role_key(role_key, ""))
    if role and role.get("report_structure"):
        return role["report_structure"]
    return ["分析摘要", "核心结论", "行动建议"]


async def generate_report(
    question: str,
    data_source_id: str,
    role_key: str = "auto",
    schedule_id: Optional[str] = None,
) -> Report:
    """
    @brief 生成并落库一份分析报告
    @param question 分析问题
    @param data_source_id 数据源 ID
    @param role_key 分析角色键
    @param schedule_id 来源定时任务 ID（手动为 None）
    @return 落库后的 Report 对象
    """
    result = await _collect_agent_result(question, data_source_id, role_key)
    resolved_role = resolve_role_key(role_key, question)

    db = SessionLocal()
    try:
        report = Report(
            schedule_id=schedule_id,
            data_source_id=data_source_id,
            title=question,
            role_key=resolved_role,
            question=question,
            summary=result["final_response"] or f"分析失败：{result['error']}",
            sections=_build_sections(resolved_role),
            charts=result["charts"],
            tables=result["tables"],
            status="success" if not result["error"] else "failed",
            error=result["error"],
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        return report
    except Exception as e:
        db.rollback()
        logger.error(f"报告落库失败: {e}")
        raise
    finally:
        db.close()
