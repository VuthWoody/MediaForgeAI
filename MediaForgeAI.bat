@echo off
title MediaForge AI
cd /d "%~dp0"

:: Set UTF-8 encoding for console output
chcp 65001 >nul 2>&1
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1
set "PYTHONPATH=%~dp0;%PYTHONPATH%"

:: Detect Python executable
set "PY_CMD=python"
if exist ".venv\Scripts\python.exe" (
    set "PY_CMD=%~dp0.venv\Scripts\python.exe"
)

:: Verify Python installation
%PY_CMD% --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python was not found in your PATH.
    echo Please install Python 3.11+ and ensure "Add python.exe to PATH" is checked.
    echo.
    pause
    exit /b 1
)

:: Verify critical dependency (PySide6)
%PY_CMD% -c "import PySide6" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [MediaForge AI] First run detected. Installing dependencies from requirements.txt...
    %PY_CMD% -m pip install -r requirements.txt
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b %ERRORLEVEL%
    )
)

:: Launch MediaForge AI Application
echo [MediaForge AI] Starting Application (with VoxReel Diarization Engine)...
%PY_CMD% main.py %*
if %ERRORLEVEL% neq 0 (
    echo.
    echo [MediaForge AI] Application exited with error code: %ERRORLEVEL%
    pause
)
