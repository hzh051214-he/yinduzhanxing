@echo off
cd /d D:\yinduzhanxing\backend
call venv\Scripts\activate.bat
celery -A app.tasks.reading_tasks.celery_app worker --loglevel=info --concurrency=2 -P solo
pause
