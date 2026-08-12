"""
@brief 数据源管理 API

GET /api/data-sources — 列表
GET /api/data-sources/{id} — 详情
DELETE /api/data-sources/{id} — 删除
GET /api/export/{id} — 导出 CSV
"""

import io
import csv
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
import pandas as pd

from app.core.database import SessionLocal
from app.models.data_source import DataSource
from app.services.data_ingestion import delete_datasource, read_datasource, infer_purpose

router = APIRouter(prefix="/api", tags=["data-sources"])


@router.get("/data-sources")
async def list_data_sources():
    """
    @brief 获取所有数据源列表
    @return [{"id": str, "name": str, "table_name": str, "row_count": int, "columns_meta": list, "created_at": str}, ...]
    """
    db = SessionLocal()
    try:
        sources = db.query(DataSource).order_by(DataSource.created_at.desc()).all()
        result = []
        for s in sources:
            # 统一以 infer_purpose 为准，旧数据或推断规则更新后自动修正
            inferred = infer_purpose(s.name, s.columns_meta)
            if s.purpose != inferred:
                s.purpose = inferred
                db.commit()
            result.append(s.to_dict())
        return result
    finally:
        db.close()


@router.get("/data-sources/{data_source_id}")
async def get_data_source(data_source_id: str):
    """
    @brief 获取单个数据源详情
    @param data_source_id 数据源 ID
    @return 数据源完整信息
    @throws HTTPException 404 如果数据源不存在
    """
    db = SessionLocal()
    try:
        source = db.query(DataSource).filter(DataSource.id == data_source_id).first()
        if source is None:
            raise HTTPException(status_code=404, detail="数据源不存在")
        return source.to_dict()
    finally:
        db.close()


@router.delete("/data-sources/{data_source_id}")
async def remove_data_source(data_source_id: str):
    """
    @brief 删除数据源（含 SQLite 表）
    @param data_source_id 数据源 ID
    @return {"message": "删除成功"}
    @throws HTTPException 404 如果数据源不存在
    """
    try:
        delete_datasource(data_source_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"message": "删除成功"}


@router.get("/export/{data_source_id}")
async def export_data_source(
    data_source_id: str,
    fmt: str = Query("csv", description="导出格式: csv"),
):
    """
    @brief 导出数据源为 CSV 文件
    @param data_source_id 数据源 ID
    @param fmt 导出格式（目前仅支持 csv）
    @return StreamingResponse（CSV 文件下载）
    """
    db = SessionLocal()
    try:
        ds = db.query(DataSource).filter(DataSource.id == data_source_id).first()
        if ds is None:
            raise HTTPException(status_code=404, detail="数据源不存在")
        filename = ds.name
    finally:
        db.close()

    try:
        df = read_datasource(data_source_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取数据失败: {str(e)}")

    # 构建 CSV 流
    stream = io.StringIO()
    df.to_csv(stream, index=False, encoding="utf-8-sig")
    stream.seek(0)

    safe_name = filename.replace(" ", "_")
    return StreamingResponse(
        iter([stream.getvalue()]),
        media_type="text/csv; charset=utf-8-sig",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}.csv"',
        },
    )
