@echo off
title MediaForge AI + VoxReel Engine
echo ===============================================================================
echo                MediaForge AI + VoxReel Diarization Engine
echo ===============================================================================
echo Launching MediaForge AI with VoxReel Actor Voice Registry...
python voxreel_app.py --allow-multiple
if %errorlevel% neq 0 (
    echo.
    echo Application exited with error code %errorlevel%.
    pause
)
