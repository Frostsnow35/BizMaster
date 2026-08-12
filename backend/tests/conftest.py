"""
@brief pytest 配置与 fixture

在所有测试运行前创建数据库表，确保 API 测试有可用的数据库环境。
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import engine, Base


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """在测试会话开始前创建所有数据库表"""
    Base.metadata.create_all(bind=engine)
    yield
    # 测试结束后清理（可选）
    Base.metadata.drop_all(bind=engine)
