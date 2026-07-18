@echo off
title FastAPI

set PY=D:\yinduzhanxing\skills\vedic-astrology\vedic-astrology-redskill\venv\Scripts\python.exe
set APP=D:\yinduzhanxing\backend

cd /d %APP%

:loop
%PY% -m uvicorn app.main:app --port 8000 --workers 1
echo FastAPI exited, restarting in 3s...
timeout /t 3 /nobreak >nul
goto loop
