@echo off
chcp 65001 >nul
echo ========================================
echo  掌柜 BizMaster - 开发环境启动
echo ========================================
echo.

REM 启动后端
echo [1/2] 启动后端服务...
start "Backend" cmd /k "cd /d %~dp0..\backend && python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"

REM 等待后端就绪
echo 等待后端服务启动...
timeout /t 3 /nobreak >nul

REM 启动前端
echo [2/2] 启动前端开发服务器...
start "Frontend" cmd /k "cd /d %~dp0..\frontend && npm run dev"

echo.
echo ========================================
echo  开发环境启动完成！
echo  前端: http://localhost:5173
echo  后端 API: http://localhost:8000/docs
echo ========================================
echo.
echo 按任意键关闭此窗口
pause >nul
