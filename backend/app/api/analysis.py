"""
@brief 同步分析 REST API

POST /api/analysis — 外部系统调用，同步返回完整分析结果。
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agent.graph import run_agent
from app.agent.tools.schema import get_all_tools
from app.api.chat import _get_data_summary

router = APIRouter(prefix="/api", tags=["analysis"])


class AnalysisRequest(BaseModel):
    """分析请求体"""
    question: str = Field(description="分析问题", min_length=1)
    data_source_id: str = Field(description="数据源 ID")


@router.post("/analysis")
async def analysis(req: AnalysisRequest):
    """
    @brief 同步分析接口

    一次性返回完整分析结果，适合外部系统调用。
    注意：同步接口中 Human Checkpoint 会自动跳过（视为拒绝）。

    @param req 分析请求 {question, data_source_id}
    @return {
        "final_response": str,
        "charts": list | None,
        "tables": list | None,
        "execution_time": float,
    }
    """
    import time
    start_time = time.time()

    data_summary = _get_data_summary(req.data_source_id)
    tools = get_all_tools()

    final_response = ""
    charts = None
    tables = None
    error_msg = None

    try:
        async for event in run_agent(
            question=req.question,
            data_source_id=req.data_source_id,
            tools=tools,
            data_summary=data_summary or "",
        ):
            event_type = event.get("type", "")

            if event_type == "done":
                final_response = event.get("final_response", "")
                charts = event.get("charts")
                tables = event.get("tables")
            elif event_type == "human_checkpoint":
                # 同步接口中自动拒绝人工审批请求
                final_response = "分析过程中触发需要人工审批的操作，在同步模式下已自动跳过。"
            elif event_type == "error":
                error_msg = event.get("message", "分析过程出错")

    except Exception as e:
        error_msg = f"分析执行异常: {str(e)}"

    execution_time = round(time.time() - start_time, 2)

    if error_msg and not final_response:
        final_response = f"分析失败：{error_msg}"

    return {
        "final_answer": final_response,
        "charts": charts,
        "tables": tables,
        "execution_time": execution_time,
    }
