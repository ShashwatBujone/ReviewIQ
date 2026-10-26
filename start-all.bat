@echo off
cd /d "%~dp0"
start "ReviewIQ backend" cmd /k call "%~dp0start-backend.bat"
timeout /t 6 /nobreak >nul
start "ReviewIQ frontend" cmd /k call "%~dp0start-frontend.bat"
timeout /t 5 /nobreak >nul
start "" http://localhost:5173
