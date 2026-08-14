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


def _apply_time(dt: datetime, time_str: str) -> datetime:
    """
    @brief 将 HH:MM 时间应用到日期，解析失败时保持原值
    @param dt 基准日期时间
    @param time_str 时间字符串 HH:MM
    @return 应用时间后的日期时间
    """
    try:
        hour, minute = (int(x) for x in time_str.split(":")[:2])
        return dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
    except (ValueError, AttributeError):
        return dt


def _next_run_time(schedule: ReportSchedule) -> datetime:
    """
    @brief 计算任务下一次到期时间
    @param schedule 定时任务
    @return 到期时间（未运行过且未指定具体时间则返回当前时间，立即执行）
    """
    interval = _FREQUENCY_INTERVALS.get(schedule.frequency, timedelta(days=1))
    has_daily_time = schedule.time and schedule.frequency in ("daily", "weekly", "monthly")

    if schedule.last_run_at is None:
        # 首次运行：未指定具体时间立即执行，否则等到当天/本周期该时刻
        if not has_daily_time:
            return datetime.now()
        target = _apply_time(datetime.now(), schedule.time)
        if target <= datetime.now():
            target += interval
        return target

    base = schedule.last_run_at + interval
    if has_daily_time:
        base = _apply_time(base, schedule.time)
    return base


async def _run_due_schedules():
    """扫描并执行所有到期任务"""
    db = SessionLocal()
    due_schedules = []
    try:
        schedules = db.query(ReportSchedule).filter(ReportSchedule.enabled == True).all()
        now = datetime.now()
        for s in schedules:
            if _next_run_time(s) <= now:
                due_schedules.append(
                    {
                        "id": s.id,
                        "question": s.question,
                        "data_source_id": s.data_source_id,
                        "role_key": s.role_key or "auto",
                    }
                )
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
            # 生成过程异常时不推进 last_run_at，下一轮重试
            logger.error(f"定时报告生成失败: {item['id']} - {e}")
            continue

        # 仅成功后推进 last_run_at，避免失败任务被静默跳过
        db = SessionLocal()
        try:
            schedule = db.query(ReportSchedule).filter(ReportSchedule.id == item["id"]).first()
            if schedule is not None:
                schedule.last_run_at = datetime.now()
                db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"更新任务运行时间失败: {item['id']} - {e}")
        finally:
            db.close()


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
