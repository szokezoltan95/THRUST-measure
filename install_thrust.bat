@echo off
setlocal
title THRUST-measure installer
echo Starting THRUST-measure installation...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_thrust.ps1"
if errorlevel 1 (
    echo.
    echo Installation failed. Review the messages above.
    pause
    exit /b 1
)
echo.
echo Installation finished. Use the THRUST-measure shortcut on your Desktop.
pause
endlocal
