@echo off
echo =====================================================================
echo Windows Memory Manager (VMM) Simulator - Launching Full-Stack System
echo =====================================================================
echo.

:: Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    pause
    exit /b 1
)

:: Install dependencies if needed
echo [INFO] Installing / verifying dependencies from backend\requirements.txt...
python -m pip install -r backend\requirements.txt --quiet

:: Run automated verification suite
echo [INFO] Running automated test suite (pytest)...
python -m pytest backend\tests -q
if %errorlevel% neq 0 (
    echo [WARNING] Some tests did not pass. Proceeding to launch server...
) else (
    echo [SUCCESS] All 22 tests passed successfully!
)

echo.
echo =====================================================================
echo [INFO] Starting FastAPI application on http://localhost:8000
echo [INFO] Interactive Swagger API Docs: http://localhost:8000/docs
echo =====================================================================
echo.

python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
pause
