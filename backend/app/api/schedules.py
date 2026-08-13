"""
@brief 定时自动报告与报告记录 API

定时任务 CRUD + 手动运行，以及报告记录查询。
"""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.database import SessionLocal
from app.models.report import ReportSchedule, Report
from app.services.report_generator import generate_report

router = APIRouter(prefix="/api", tags=["schedules"])

ALLOWED_FREQUENCIES = {"hourly", "daily", "weekly", "monthly"}


class ScheduleCreate(BaseModel):
    """创建定时任务请求体"""
    name: str = Field(description="任务名称", min_length=1)
    data_source_id: str = Field(description="数据源 ID")
    question: str = Field(description="分析问题", min_length=1)
    role_key: str = Field(default="auto", description="分析角色键")
    frequency: str = Field(default="daily", description="频率: hourly/daily/weekly/monthly")
    time: Optional[str] = Field(default=None, description="执行时间 HH:MM")


class ScheduleUpdate(BaseModel):
    """更新定时任务请求体"""
    name: Optional[str] = None
    data_source_id: Optional[str] = None
    question: Optional[str] = None
    role_key: Optional[str] = None
    frequency: Optional[str] = None
    time: Optional[str] = None
    enabled: Optional[bool] = None


def _validate_frequency(frequency: str):
    if frequency not in ALLOWED_FREQUENCIES:
        raise HTTPException(status_code=400, detail=f"无效频率: {frequency}，可选 {ALLOWED_FREQUENCIES}")


@router.get("/schedules")
async def list_schedules():
    """
    @brief 获取所有定时任务
    @return 定时任务列表
    """
    db = SessionLocal()
    try:
        schedules = db.query(ReportSchedule).order_by(ReportSchedule.created_at.desc()).all()
        return [s.to_dict() for s in schedules]
    finally:
        db.close()


@router.post("/schedules")
async def create_schedule(req: ScheduleCreate):
    """
    @brief 创建定时任务
    @param req 任务信息
    @return 创建后的任务
    """
    _validate_frequency(req.frequency)
    db = SessionLocal()
    try:
        schedule = ReportSchedule(
            name=req.name,
            data_source_id=req.data_source_id,
            question=req.question,
            role_key=req.role_key or "auto",
            frequency=req.frequency,
            time=req.time,
            enabled=True,
        )
        db.add(schedule)
        db.commit()
        db.refresh(schedule)
        return schedule.to_dict()
    finally:
        db.close()


@router.put("/schedules/{schedule_id}")
async def update_schedule(schedule_id: str, req: ScheduleUpdate):
    """
    @brief 更新定时任务
    @param schedule_id 任务 ID
    @param req 更新字段
    @return 更新后的任务
    """
    db = SessionLocal()
    try:
        schedule = db.query(ReportSchedule).filter(ReportSchedule.id == schedule_id).first()
        if schedule is None:
            raise HTTPException(status_code=404, detail="定时任务不存在")

        updates = req.model_dump(exclude_unset=True)
        if "frequency" in updates and updates["frequency"] is not None:
            _validate_frequency(updates["frequency"])
        for field, value in updates.items():
            setattr(schedule, field, value)
        db.commit()
        db.refresh(schedule)
        return schedule.to_dict()
    finally:
        db.close()


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(schedule_id: str):
    """
    @brief 删除定时任务
    @param schedule_id 任务 ID
    @return {"message": "删除成功"}
    """
    db = SessionLocal()
    try:
        schedule = db.query(ReportSchedule).filter(ReportSchedule.id == schedule_id).first()
        if schedule is None:
            raise HTTPException(status_code=404, detail="定时任务不存在")
        db.delete(schedule)
        db.commit()
        return {"message": "删除成功"}
    finally:
        db.close()


@router.post("/schedules/{schedule_id}/run")
async def run_schedule_now(schedule_id: str):
    """
    @brief 立即运行定时任务，生成一份报告
    @param schedule_id 任务 ID
    @return 生成的报告
    """
    db = SessionLocal()
    try:
        schedule = db.query(ReportSchedule).filter(ReportSchedule.id == schedule_id).first()
        if schedule is None:
            raise HTTPException(status_code=404, detail="定时任务不存在")
        question = schedule.question
        data_source_id = schedule.data_source_id
        role_key = schedule.role_key or "auto"
        from datetime import datetime

        schedule.last_run_at = datetime.now()
        db.commit()
    finally:
        db.close()

    report = await generate_report(
        question=question,
        data_source_id=data_source_id,
        role_key=role_key,
        schedule_id=schedule_id,
    )
    return report.to_dict()


@router.get("/reports")
async def list_reports():
    """
    @brief 获取所有分析报告
    @return 报告列表（不含完整内容）
    """
    db = SessionLocal()
    try:
        reports = db.query(Report).order_by(Report.created_at.desc()).all()
        return [r.to_dict() for r in reports]
    finally:
        db.close()


@router.get("/reports/{report_id}")
async def get_report(report_id: str):
    """
    @brief 获取单个报告详情
    @param report_id 报告 ID
    @return 报告完整内容
    """
    db = SessionLocal()
    try:
        report = db.query(Report).filter(Report.id == report_id).first()
        if report is None:
            raise HTTPException(status_code=404, detail="报告不存在")
        return report.to_dict()
    finally:
        db.close()
