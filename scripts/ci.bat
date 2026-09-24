@echo off
echo === 1. Ruff Check ===
ruff check core/ ui/ modules/ tests/ scripts/ app.py
if %ERRORLEVEL% neq 0 exit /b %ERRORLEVEL%

echo === 2. MyPy Strict Core ===
mypy --strict core/
if %ERRORLEVEL% neq 0 exit /b %ERRORLEVEL%

echo === 3. Pytest with Coverage ===
pytest tests/unit/
if %ERRORLEVEL% neq 0 exit /b %ERRORLEVEL%

echo === CI Passed Successfully ===
