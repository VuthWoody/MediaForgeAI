@echo off
title MediaForge AI — Unit Tests
cd /d "%~dp0"
python -m pytest tests/unit/ -v
echo.
pause
