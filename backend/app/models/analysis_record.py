"""
@brief 分析记录 ORM 模型（对话消息）
"""
from sqlalchemy import Column, String, Integer, DateTime, Text
from datetime import datetime

from app.core.database import Base
from app.models.data_source import generate_uuid


class AnalysisRecord(Base):
    __tablename__ = "analysis_records"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), nullable=False, index=True, comment="会话 ID")
    role = Column(String(20), nullable=False, comment="角色: user / assistant / system")
    content = Column(Text, nullable=False, comment="消息内容（JSON 字符串）")
    msg_type = Column(String(30), default="text", comment="消息类型: text/chart/table/error/thinking")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "msg_type": self.msg_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
