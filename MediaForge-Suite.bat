@echo off
title MediaForge AI - Control Suite
cd /d "%~dp0"

chcp 65001 >nul 2>&1
set PYTHONUTF8=1
set PYTHONUNBUFFERED=1

set "PY_CMD=python"
if exist "%~dp0.venv\Scripts\python.exe" (
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

:: Run the interactive control suite
%PY_CMD% scripts\suite_menu.py %*
if %ERRORLEVEL% neq 0 (
    echo.
    echo [MediaForge AI] Control Suite exited with code: %ERRORLEVEL%
    pause
)
