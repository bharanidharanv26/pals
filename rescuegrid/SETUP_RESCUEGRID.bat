@echo off
setlocal
python "%~dp0scripts\setup.py"
if errorlevel 1 (
  echo Setup failed. Review the message above.
  pause
  exit /b 1
)
echo Ready. Open START_RESCUEGRID.bat to run the application.
pause
