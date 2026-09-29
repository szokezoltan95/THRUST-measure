@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo THRUST-measure is not installed yet. Run install_thrust.bat first.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" "scripts\import_measurements.py" %*
echo.
pause
endlocal
