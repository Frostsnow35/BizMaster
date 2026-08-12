"""
@brief API 集成测试
"""
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestHealthCheck:
    """健康检查测试"""

    def test_health_returns_200(self):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestDataSourceAPI:
    """数据源管理 API 测试"""

    def test_list_data_sources_empty(self):
        response = client.get("/api/data-sources")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_nonexistent_returns_404(self):
        response = client.get("/api/data-sources/nonexistent-id")
        assert response.status_code == 404


class TestUploadAPI:
    """文件上传 API 测试"""

    def test_upload_no_file(self):
        response = client.post("/api/upload")
        assert response.status_code == 422  # FastAPI 验证错误

    def test_upload_invalid_format(self):
        import io
        file_content = io.BytesIO(b"test content")
        response = client.post(
            "/api/upload",
            files={"file": ("test.txt", file_content, "text/plain")},
        )
        assert response.status_code == 400
        assert "不支持" in response.json()["detail"]
