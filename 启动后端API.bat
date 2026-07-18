@echo off
cd /d D:\yinduzhanxing\backend
call venv\Scripts\activate.bat
uvicorn app.main:app --reload --port 8000
pause
