@echo off
cd /d "%~dp0"
py -m venv .venv
if errorlevel 1 (echo Python 3.11+ is required. & pause & exit /b 1)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (echo Dependency install failed. & pause & exit /b 1)
echo Setup completed. Double-click start_windows.bat to launch.
pause
