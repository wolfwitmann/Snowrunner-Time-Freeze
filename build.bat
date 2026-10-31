@echo off
rem Builds dist\SnowRunnerTimeLock.exe on your own PC (needs Python installed).
cd /d "%~dp0"
python -m pip install --upgrade pymem pyinstaller
python -m PyInstaller --onefile --console --name SnowRunnerTimeLock sr_timelock.py
echo.
echo Done. Your exe is in the dist folder.
pause
