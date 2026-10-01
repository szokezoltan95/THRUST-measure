@echo off
setlocal
title THRUST-measure installer
if not exist "%~dp0EULA.txt" (
    echo EULA.txt is missing from the installer folder.
    pause
    exit /b 1
)
more < "%~dp0EULA.txt"
echo.
choice /C YN /N /M "Continue installation after reading the license? [Y/N] "
if errorlevel 2 (
    echo Installation cancelled.
    exit /b 0
)
if errorlevel 1 goto install
echo Installation cancelled.
exit /b 1
:install
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
