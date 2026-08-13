"""
@brief 数据看板 API

POST /api/dashboard 根据多个数据源生成智能经营看板。
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.dashboard import build_dashboard

router = APIRouter(prefix="/api", tags=["dashboard"])


class DashboardRequest(BaseModel):
    """看板生成请求体"""
    data_source_ids: list[str] = Field(description="数据源 ID 列表")


@router.post("/dashboard")
async def create_dashboard(req: DashboardRequest):
    """
    @brief 生成数据看板
    @param req 看板请求体，含数据源 ID 列表
    @return {"insight", "sections", "errors"}
    @throws HTTPException 400 当数据源列表为空
    """
    if not req.data_source_ids:
        raise HTTPException(status_code=400, detail="至少选择一个数据源")

    return await build_dashboard(req.data_source_ids)
