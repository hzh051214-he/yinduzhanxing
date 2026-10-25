#!/bin/sh
# 单容器启动：Celery Worker（后台） + uvicorn API（前台）
# Railway Volume 挂载在 /app/storage，两个进程天然共享文件。

set -e

echo "[start_both] launching celery worker..."
celery -A app.tasks.reading_tasks.celery_app worker \
    --loglevel=info --concurrency=2 -Q default &
CELERY_PID=$!

echo "[start_both] launching uvicorn api..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1
