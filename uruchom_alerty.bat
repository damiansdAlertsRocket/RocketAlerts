@echo off
cd /d %~dp0

echo.
echo Uruchamianie RocketAlerts...
py --version

echo.
echo Uruchamiam scheduler.py...
py scheduler.py

echo.
pause
