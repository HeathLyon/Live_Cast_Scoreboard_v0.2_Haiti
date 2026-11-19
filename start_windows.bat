@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" app.py
) else (
  echo Virtual environment not found. Follow README setup steps first.
  pause
  exit /b 1
)
if errorlevel 1 pause
