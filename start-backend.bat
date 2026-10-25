@echo off
REM CareerPilot AI — start backend (FastAPI on :8010). Run from project root.
REM TF log vars keep the demo console clean (set before TF import).
set TF_CPP_MIN_LOG_LEVEL=3
set TF_ENABLE_ONEDNN_OPTS=0
set PYTHONWARNINGS=ignore::FutureWarning
cd /d "%~dp0backend"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8010
