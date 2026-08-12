"""
@brief 数据源 ORM 模型
"""
from sqlalchemy import Column, String, Integer, DateTime, JSON, Text
from sqlalchemy.orm import declarative_base
from datetime import datetime
import uuid

from app.core.database import Base


def generate_uuid():
    return str(uuid.uuid4())


class DataSource(Base):
    __tablename__ = "data_sources"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False, comment="数据源名称")
    file_path = Column(String(500), nullable=True, comment="原始文件路径")
    file_type = Column(String(20), nullable=True, comment="文件类型: csv/xlsx")
    file_size_kb = Column(Integer, nullable=True, comment="文件大小(KB)")
    table_name = Column(String(100), nullable=False, unique=True, comment="对应 SQLite 表名")
    row_count = Column(Integer, default=0, comment="数据行数")
    columns_meta = Column(JSON, nullable=True, comment="列元信息 [{name, type, nullable}]")
    purpose = Column(String(100), nullable=True, comment="数据源用途（上传时推断）")
    platform = Column(String(50), nullable=True, comment="数据来源平台: taobao/pinduoduo/douyin/jd/generic")
    column_mapping = Column(JSON, nullable=True, comment="列名映射 {原始列名: 标准列名}")
    created_at = Column(DateTime, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "file_type": self.file_type,
            "file_size_kb": self.file_size_kb,
            "table_name": self.table_name,
            "row_count": self.row_count,
            "columns_meta": self.columns_meta,
            "purpose": self.purpose,
            "platform": self.platform,
            "column_mapping": self.column_mapping,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
