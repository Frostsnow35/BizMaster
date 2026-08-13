"""
@brief FastAPI 应用入口

掌柜 BizMaster 后端服务。
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import config
from app.core.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    @brief 应用生命周期管理
    启动时初始化数据库并启动定时调度器，关闭时清理资源。
    """
    # 启动
    init_db()
    from app.services.scheduler import start_scheduler, stop_scheduler
    start_scheduler()
    yield
    # 关闭
    stop_scheduler()


app = FastAPI(
    title=config.app.name,
    version=config.app.version,
    description="面向中小电商商家的自助经营数据分析智能体",
    lifespan=lifespan,
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        # Electron 生产模式以 file:// 加载，Origin 为字符串 "null"
        "null",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    """
    @brief 健康检查端点
    @return {"status": "ok", "version": "..."}
    """
    return {
        "status": "ok",
        "version": config.app.version,
    }


# 注册上传路由
from app.api.upload import router as upload_router

app.include_router(upload_router)

from app.api.data_source import router as data_source_router
app.include_router(data_source_router)

from app.api.chat import router as chat_router
app.include_router(chat_router)

from app.api.analysis import router as analysis_router
app.include_router(analysis_router)

from app.api.config import router as config_router
app.include_router(config_router)

from app.api.templates import router as templates_router
app.include_router(templates_router)

from app.api.schedules import router as schedules_router
app.include_router(schedules_router)

from app.api.dashboard import router as dashboard_router
app.include_router(dashboard_router)

from app.api.forecast import router as forecast_router
app.include_router(forecast_router)


if __name__ == "__main__":
    """
    @brief 本地/PyInstaller 启动入口
    打包后的 backend.exe 依赖此入口启动 uvicorn 服务。
    """
    import sys
    import os
    import tempfile
    import traceback

    # PyInstaller windowed 模式下 stdout/stderr 为 None，重定向到日志文件便于排障
    if getattr(sys, "frozen", False) and (sys.stdout is None or sys.stderr is None):
        log_file = open(
            os.path.join(tempfile.gettempdir(), "ecom-agent-backend.log"),
            "w",
            encoding="utf-8",
        )
        sys.stdout = log_file
        sys.stderr = log_file

    try:
        import uvicorn

        uvicorn.run(app, host="127.0.0.1", port=8000)
    except Exception:
        traceback.print_exc()
        raise
