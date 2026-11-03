@echo off
setlocal
if not exist "%~dp0.venv\Scripts\python.exe" (
  echo RescueGrid's Python environment was not found.
  pause
  exit /b 1
)
"%~dp0.venv\Scripts\python.exe" "%~dp0scripts\launch.py" --stop --no-browser %*
if errorlevel 1 pause
