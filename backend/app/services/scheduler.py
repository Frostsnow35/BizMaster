"""
@brief 定时自动报告调度器

基于 asyncio 后台循环，周期性扫描到期任务并触发报告生成。
不依赖外部调度库，便于 PyInstaller 打包。
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from app.core.database import SessionLocal
from app.models.report import ReportSchedule
from app.services.report_generator import generate_report

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 60

_FREQUENCY_INTERVALS = {
    "hourly": timedelta(hours=1),
    "daily": timedelta(days=1),
    "weekly": timedelta(weeks=1),
    "monthly": timedelta(days=30),
}


def _next_run_time(schedule: ReportSchedule) -> datetime:
    """
    @brief 计算任务下一次到期时间
    @param schedule 定时任务
    @return 到期时间（未运行过则返回当前时间，立即执行）
    """
    interval = _FREQUENCY_INTERVALS.get(schedule.frequency, timedelta(days=1))
    if schedule.last_run_at is None:
        return datetime.now()
    return schedule.last_run_at + interval


async def _run_due_schedules():
    """扫描并执行所有到期任务"""
    db = SessionLocal()
    due_schedules = []
    try:
        schedules = db.query(ReportSchedule).filter(ReportSchedule.enabled == True).all()
        now = datetime.now()
        for s in schedules:
            if _next_run_time(s) <= now:
                s.last_run_at = now
                due_schedules.append(
                    {
                        "id": s.id,
                        "question": s.question,
                        "data_source_id": s.data_source_id,
                        "role_key": s.role_key or "auto",
                    }
                )
        if due_schedules:
            db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"调度扫描失败: {e}")
        due_schedules = []
    finally:
        db.close()

    for item in due_schedules:
        try:
            await generate_report(
                question=item["question"],
                data_source_id=item["data_source_id"],
                role_key=item["role_key"],
                schedule_id=item["id"],
            )
            logger.info(f"定时报告已生成: {item['id']} - {item['question'][:20]}")
        except Exception as e:
            logger.error(f"定时报告生成失败: {item['id']} - {e}")


async def scheduler_loop():
    """调度器主循环"""
    while True:
        try:
            await _run_due_schedules()
        except Exception as e:
            logger.error(f"调度循环异常: {e}")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


_scheduler_task: Optional[asyncio.Task] = None


def start_scheduler():
    """
    @brief 启动后台调度器（应用生命周期内调用）
    """
    global _scheduler_task
    if _scheduler_task is None or _scheduler_task.done():
        _scheduler_task = asyncio.create_task(scheduler_loop())


def stop_scheduler():
    """
    @brief 停止后台调度器（应用关闭时调用）
    """
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
