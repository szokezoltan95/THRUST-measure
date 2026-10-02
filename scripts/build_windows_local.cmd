@echo off
setlocal
pushd "%~dp0.." || exit /b 1

rem Reproduce the Windows PyInstaller step without creating a GitHub release.
rem Requires the 64-bit Python 3.12 launcher and an internet connection for pip.
py -3.12-64 --version >nul 2>&1
if errorlevel 1 (
    echo Python 3.12 x64 is required. Install it and try again.
    goto :fail
)

set "BUILD_PYTHON=.local-build\venv\Scripts\python.exe"
if not exist "%BUILD_PYTHON%" (
    py -3.12-64 -m venv ".local-build\venv"
    if errorlevel 1 goto :fail
)

"%BUILD_PYTHON%" -m pip install ".[gui]" pyinstaller
if errorlevel 1 goto :fail

"%BUILD_PYTHON%" scripts\render_splash.py ".release-assets\splash.png"
if errorlevel 1 goto :fail
echo.
echo Generated splash image: %CD%\.release-assets\splash.png
echo Check this PNG if the text looks wrong in the executable.
echo.

"%BUILD_PYTHON%" -m PyInstaller --noconfirm --clean --windowed --onedir --name THRUST-measure --icon "%CD%\THRUST.ico" --splash "%CD%\.release-assets\splash.png" --add-data "%CD%\THRUST.ico;." --add-data "%CD%\profiles;profiles" --collect-data thrust --distpath "%CD%\.local-build\dist" --workpath "%CD%\.local-build\work" --specpath "%CD%\.local-build" "%CD%\main.py"
if errorlevel 1 goto :fail

echo.
echo Test executable: %CD%\.local-build\dist\THRUST-measure\THRUST-measure.exe
echo This build does not install the app or create a GitHub release.
popd
exit /b 0

:fail
echo Local Windows build failed.
popd
exit /b 1
