@echo off
rem Job Copilot one-click launcher - double-click to start
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual env not found.
    echo Please run: pip install -r requirements.txt
    pause
    exit /b 1
)

echo Starting Job Copilot...
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\run.ps1"

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Startup failed. See messages above.
    pause
    exit /b 1
)

echo.
echo Job Copilot is running in the background.
echo You can close this window; the service keeps running.
pause
