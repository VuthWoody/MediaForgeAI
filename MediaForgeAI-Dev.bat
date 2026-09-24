@echo off
title MediaForge AI (Dev Console Mode)
cd /d "%~dp0"

chcp 65001 >nul 2>&1
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1
set MEDIAFORGE_DEV=1
set "PYTHONPATH=%~dp0;%PYTHONPATH%"

set "PY_CMD=python"
if exist ".venv\Scripts\python.exe" (
    set "PY_CMD=%~dp0.venv\Scripts\python.exe"
)

echo [MediaForge AI] Launching in Developer Console Mode (MEDIAFORGE_DEV=1)...
echo.
%PY_CMD% main.py --allow-multiple %*
if %ERRORLEVEL% neq 0 (
    echo.
    echo [MediaForge AI] Process terminated with error code: %ERRORLEVEL%
)
echo.
pause
