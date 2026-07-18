@echo off
title Celery

set PY=D:\yinduzhanxing\skills\vedic-astrology\vedic-astrology-redskill\venv\Scripts\python.exe
set APP=D:\yinduzhanxing\backend

cd /d %APP%

%PY% -m celery -A app.tasks.reading_tasks.celery_app worker --loglevel=info --concurrency=1 -P solo
pause
