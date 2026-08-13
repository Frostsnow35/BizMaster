"""
@brief 预测分析 API

POST /api/forecast 基于单个数据源生成未来趋势预测。
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.forecast import build_forecast

router = APIRouter(prefix="/api", tags=["forecast"])


class ForecastRequest(BaseModel):
    """预测请求体"""
    data_source_id: str = Field(description="数据源 ID")
    metric: str = Field(default="sales", description="指标: sales/orders/qty")
    periods: int = Field(default=30, ge=1, le=365, description="预测期数")
    method: str = Field(default="linear", description="方法: linear/moving_avg")
    freq: str = Field(default="D", description="时间粒度: D/W/M")


@router.post("/forecast")
async def create_forecast(req: ForecastRequest):
    """
    @brief 生成趋势预测
    @param req 预测请求体
    @return 预测响应结构
    @throws HTTPException 400 当预测参数不合法或数据源缺少必要列
    """
    try:
        return await build_forecast(
            data_source_id=req.data_source_id,
            metric=req.metric,
            periods=req.periods,
            method=req.method,
            freq=req.freq,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
