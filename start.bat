@echo off
echo ========================================================
echo   Starting Frontdesk (Arvo Systems Support Management)
echo ========================================================
echo.
echo Installing Python dependencies...
python -m pip install -r backend\requirements.txt
echo.
echo Starting application on http://127.0.0.1:8000 ...
python run_local.py
pause
