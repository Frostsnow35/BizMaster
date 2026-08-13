"""
@brief 定时报告与报告记录 ORM 模型
"""
from sqlalchemy import Column, String, DateTime, Text, Boolean, JSON
from datetime import datetime

from app.core.database import Base
from app.models.data_source import generate_uuid


class ReportSchedule(Base):
    """定时自动报告任务"""
    __tablename__ = "report_schedules"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(100), nullable=False, comment="定时任务名称")
    data_source_id = Column(String(36), nullable=False, index=True, comment="数据源 ID")
    question = Column(Text, nullable=False, comment="分析问题")
    role_key = Column(String(30), default="auto", comment="分析角色键")
    frequency = Column(String(20), nullable=False, comment="频率: hourly/daily/weekly/monthly")
    time = Column(String(5), nullable=True, comment="执行时间 HH:MM（每日/每周/每月）")
    enabled = Column(Boolean, default=True, comment="是否启用")
    last_run_at = Column(DateTime, nullable=True, comment="上次运行时间")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "data_source_id": self.data_source_id,
            "question": self.question,
            "role_key": self.role_key,
            "frequency": self.frequency,
            "time": self.time,
            "enabled": self.enabled,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Report(Base):
    """分析报告记录"""
    __tablename__ = "reports"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    schedule_id = Column(String(36), nullable=True, index=True, comment="来源定时任务 ID（手动为 null）")
    data_source_id = Column(String(36), nullable=False, index=True, comment="数据源 ID")
    title = Column(String(255), nullable=False, comment="报告标题")
    role_key = Column(String(30), default="data_analyst", comment="分析角色键")
    question = Column(Text, nullable=True, comment="分析问题")
    summary = Column(Text, nullable=True, comment="报告摘要")
    sections = Column(JSON, nullable=True, comment="报告章节结构")
    charts = Column(JSON, nullable=True, comment="图表数据")
    tables = Column(JSON, nullable=True, comment="表格数据")
    status = Column(String(20), default="success", comment="状态: success/failed")
    error = Column(Text, nullable=True, comment="错误信息")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    def to_dict(self):
        return {
            "id": self.id,
            "schedule_id": self.schedule_id,
            "data_source_id": self.data_source_id,
            "title": self.title,
            "role_key": self.role_key,
            "question": self.question,
            "summary": self.summary,
            "sections": self.sections,
            "charts": self.charts,
            "tables": self.tables,
            "status": self.status,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
