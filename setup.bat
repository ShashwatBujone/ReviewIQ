@echo off
setlocal
cd /d "%~dp0"
echo ============================================
echo   ReviewIQ - one-time setup (Windows)
echo ============================================

rem ---- pick a supported Python (3.10-3.14), preferring 3.13 ----
set "PY="
for %%V in (3.13 3.12 3.11 3.14 3.10) do (
  if not defined PY ( py -%%V -c "import sys" >nul 2>nul && set "PY=py -%%V" )
)
if not defined PY ( where python >nul 2>nul && set "PY=python" )
if not defined PY (
  echo [ERROR] Python was not found. Install Python 3.13 from https://www.python.org/downloads/
  echo         and tick "Add python.exe to PATH" during installation.
  pause & exit /b 1
)
%PY% -c "import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] <= (3,14) else 1)" || (
  echo [ERROR] ReviewIQ needs Python 3.10 - 3.14. Found:
  %PY% --version
  echo         Newer versions do not have pre-built packages yet. Install Python 3.13 with:
  echo             py install 3.13
  echo         or from https://www.python.org/downloads/ , then run setup.bat again.
  pause & exit /b 1
)
echo Using Python:
%PY% --version

where npm >nul 2>nul || (
  echo [ERROR] Node.js / npm was not found. Install Node.js 18+ LTS from https://nodejs.org/
  pause & exit /b 1
)

echo.
echo [1/3] Creating Python virtual environment in backend\.venv ...
cd backend
rem Remove a venv left over from an unsupported Python version
if exist .venv\Scripts\python.exe (
  .venv\Scripts\python.exe -c "import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] <= (3,14) else 1)" || (
    echo Removing old virtual environment made with an unsupported Python version ...
    rmdir /s /q .venv
  )
)
if not exist .venv\Scripts\python.exe (
  %PY% -m venv .venv || (echo [ERROR] venv creation failed & pause & exit /b 1)
)
.venv\Scripts\python.exe -m pip install --upgrade pip
echo.
echo [2/3] Installing backend packages ...
.venv\Scripts\python.exe -m pip install --only-binary=:all: -r requirements.txt || (
  echo [ERROR] pip install failed. If it mentions "Microsoft Visual C++", your Python version is too new:
  echo         install Python 3.13 ^(py install 3.13^), delete backend\.venv and run setup.bat again.
  pause & exit /b 1
)
if not exist .env copy .env.example .env >nul

echo.
echo [3/3] Installing frontend packages ...
cd ..\frontend
if not exist .env copy .env.example .env >nul
call npm install || (echo [ERROR] npm install failed & pause & exit /b 1)

cd ..
echo.
echo Setup complete. Start the app with start-all.bat
pause
