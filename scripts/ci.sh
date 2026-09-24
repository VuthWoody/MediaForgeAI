#!/usr/bin/env bash
set -e

echo "=== 1. Ruff Check ==="
ruff check core/ ui/ modules/ tests/ scripts/ app.py

echo "=== 2. MyPy Strict Core ==="
mypy --strict core/

echo "=== 3. Pytest with Coverage ==="
pytest tests/unit/
