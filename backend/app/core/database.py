"""
@brief SQLite 数据库引擎与会话管理模块
"""
import sqlite3
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import config
import os

# 确保 data 目录存在
db_path = config.database.sqlite_path
db_dir = os.path.dirname(db_path)
if db_dir and not os.path.exists(db_dir):
    os.makedirs(db_dir, exist_ok=True)

# 创建引擎（SQLite 需要 check_same_thread=False 以支持多线程）
engine = create_engine(
    f"sqlite:///{db_path}",
    connect_args={"check_same_thread": False},
    echo=config.app.debug,
)

# 会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 声明式基类
Base = declarative_base()


def _migrate_columns():
    """
    @brief 对已有表执行增量列迁移
    在不破坏已有数据的前提下补齐新增字段。
    """
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        # 检查 data_sources 表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='data_sources'")
        if cursor.fetchone():
            existing = {r[1] for r in cursor.execute("PRAGMA table_info('data_sources')")}
            new_columns = [
                ("file_type", "VARCHAR(20)"),
                ("file_size_kb", "INTEGER"),
                ("purpose", "VARCHAR(100)"),
                ("platform", "VARCHAR(50)"),
                ("column_mapping", "TEXT"),
            ]
            for col_name, col_type in new_columns:
                if col_name not in existing:
                    cursor.execute(f"ALTER TABLE data_sources ADD COLUMN {col_name} {col_type}")
                    print(f"[数据库迁移] 已为 data_sources 添加列: {col_name}")
        conn.commit()
    finally:
        conn.close()


def init_db():
    """
    @brief 初始化数据库，创建所有表 + 增量迁移
    """
    Base.metadata.create_all(bind=engine)
    try:
        _migrate_columns()
    except Exception as e:
        print(f"[数据库迁移] 警告 - 列迁移失败（如为新数据库可忽略）: {e}")


def get_db():
    """
    @brief 获取数据库会话（FastAPI 依赖注入用）
    @yield SQLAlchemy Session 对象
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
