@echo off
setlocal
cd /d "%~dp0"
echo.
echo  Client Intake - installer
echo  =========================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo  Python is not installed.
    echo  Install Python 3.10 or newer from https://www.python.org/downloads/
    echo  and tick "Add python.exe to PATH" during setup. Then run this file again.
    echo.
    pause
    exit /b 1
)

echo  Installing required packages...
python -m pip install --quiet --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
    echo  Package install failed. See the message above.
    pause
    exit /b 1
)

echo  Creating shortcuts...
for /f "delims=" %%P in ('python -c "import sys, pathlib; print(pathlib.Path(sys.executable).with_name('pythonw.exe'))"') do set "PYW=%%P"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0create_shortcuts.ps1" -PythonW "%PYW%"
if errorlevel 1 (
    echo  Could not create shortcuts. You can still run client_intake.pyw directly.
)

echo.
echo  Done. Open "Client Intake" from your desktop or Start menu.
echo  On first launch, choose your Clients folder.
echo.
pause
