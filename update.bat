@echo off
cd /d "%~dp0"
where git >nul 2>nul
if errorlevel 1 (
    echo  Git is not installed. Download the latest ZIP from GitHub instead
    echo  and copy it over this folder, then run install.bat.
    pause
    exit /b 1
)
git pull
python -m pip install --quiet --disable-pip-version-check -r requirements.txt
echo.
echo  Client Intake is up to date.
pause
