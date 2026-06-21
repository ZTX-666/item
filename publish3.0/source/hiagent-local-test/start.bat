@echo off
cd /d "%~dp0"
echo Installing deps (first run may take a minute)...
python -m pip install -r requirements.txt -q
echo.
python local_test_server.py
pause
