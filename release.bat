@echo off
rem Publish a new version of Client Intake (builds the exe and creates the GitHub Release).
cd /d "%~dp0"
python release.py %*
echo.
pause
