"""
@brief 一键分析模板 API

GET /api/templates — 返回预设分析场景模板清单
"""

from fastapi import APIRouter

from app.agent.templates import get_templates

router = APIRouter(prefix="/api", tags=["templates"])


@router.get("/templates")
async def list_templates():
    """
    @brief 查询全部一键分析模板
    @return 模板清单列表
    """
    return get_templates()
