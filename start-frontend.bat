@echo off
cd /d "%~dp0frontend"
if not exist node_modules (
  echo Frontend is not set up yet. Run setup.bat first.
  pause & exit /b 1
)
echo Starting ReviewIQ web app on http://localhost:5173
call npm run dev
pause
