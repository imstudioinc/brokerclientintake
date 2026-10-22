@echo off
rem Builds dist\ClientIntake (a folder with ClientIntake.exe) and ClientIntake-windows.zip.
rem Only needed on a computer WITH Python, to make the version for computers without it.
setlocal
cd /d "%~dp0"

python -m pip install --quiet --disable-pip-version-check -r requirements.txt pyinstaller==6.22.3
if errorlevel 1 goto :fail

python -m PyInstaller --noconfirm --clean --windowed --name ClientIntake --distpath release ^
  --icon templates\app.ico ^
  --add-data "templates;templates" ^
  --collect-data customtkinter ^
  --collect-data pdfminer ^
  --hidden-import win32com.client ^
  client_intake.pyw
if errorlevel 1 goto :fail

if exist ClientIntake-windows.zip del ClientIntake-windows.zip
powershell -NoProfile -Command "Compress-Archive -Path 'dist\ClientIntake' -DestinationPath 'ClientIntake-windows.zip'"
echo.
echo  Built: dist\ClientIntake\ClientIntake.exe
echo  Zip:   ClientIntake-windows.zip
exit /b 0

:fail
echo  Build failed. See the messages above.
exit /b 1
