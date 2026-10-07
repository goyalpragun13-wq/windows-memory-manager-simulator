#!/usr/bin/env bash
set -e

echo "====================================================================="
echo "Windows Memory Manager (VMM) Simulator - Full-Stack Launch Script"
echo "====================================================================="
echo ""

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] python3 could not be found."
    exit 1
fi

echo "[INFO] Installing / verifying dependencies..."
python3 -m pip install -r backend/requirements.txt --quiet

echo "[INFO] Running verification tests..."
python3 -m pytest backend/tests -q

echo ""
echo "====================================================================="
echo "[INFO] Launching FastAPI application at http://localhost:8000"
echo "[INFO] Interactive API Docs at http://localhost:8000/docs"
echo "====================================================================="
echo ""

exec python3 -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --reload
