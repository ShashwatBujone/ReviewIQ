@echo off
cd /d "%~dp0"
if not exist backend\.venv\Scripts\python.exe (
  echo Run setup.bat first.
  pause & exit /b 1
)
backend\.venv\Scripts\python.exe -m pytest -v
pause
