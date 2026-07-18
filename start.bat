@echo off
chcp 65001 >nul
title 吠陀占星 - 服务启动器

set VENV_PY=D:\yinduzhanxing\skills\vedic-astrology\vedic-astrology-redskill\venv\Scripts\python.exe
set BACKEND=D:\yinduzhanxing\backend

echo ==========================================
echo  吠陀占星网站 - 一键启动
echo ==========================================
echo.

REM 检查 Redis
echo [1/3] 检查 Redis...
%VENV_PY% -c "import redis; r=redis.from_url('redis://localhost:6379/0'); r.ping(); print('  Redis OK')" 2>nul
if errorlevel 1 (
    echo  [错误] Redis 未运行，请先启动 Memurai
    echo  Memurai 通常会自动作为 Windows 服务运行
    echo  可在任务管理器的服务标签页中检查 Memurai 是否启动
    pause
    exit /b 1
)

REM 终止已有的 uvicorn 和 celery 进程
echo.
echo [2/3] 清理旧进程...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq FastAPI*" >nul 2>&1
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":8000 "') do (
    taskkill /F /PID %%p >nul 2>&1
)
timeout /t 1 /nobreak >nul

echo.
echo [3/3] 启动服务...
echo.

REM 启动 FastAPI（新窗口）
echo  启动 FastAPI (http://localhost:8000)...
start "FastAPI" cmd /k "cd /d %BACKEND% && %VENV_PY% -m uvicorn app.main:app --port 8000 --workers 1"

timeout /t 3 /nobreak >nul

REM 启动 Celery Worker（新窗口）
echo  启动 Celery Worker...
start "Celery" cmd /k "cd /d %BACKEND% && %VENV_PY% -m celery -A app.tasks.reading_tasks.celery_app worker --loglevel=info --concurrency=1 -P solo --include=app.tasks.ai_analysis_tasks"

timeout /t 3 /nobreak >nul

REM 启动前端（新窗口）
echo  启动前端 (http://localhost:5173)...
start "Frontend" cmd /k "cd /d D:\yinduzhanxing\frontend && npm run dev"

echo.
echo ==========================================
echo  所有服务已启动！
echo  浏览器访问: http://localhost:5173
echo ==========================================
echo.
echo  [重启服务] 关闭所有服务窗口后，再次运行此脚本
echo  [查看日志] 查看对应的 FastAPI / Celery 窗口
echo.
pause
