@echo off
cd /d "%~dp0backend"
if not exist .venv\Scripts\python.exe (
  echo Backend is not set up yet. Run setup.bat first.
  pause & exit /b 1
)
echo Starting ReviewIQ API on http://localhost:8000  (Swagger docs: http://localhost:8000/docs)
.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000
pause
