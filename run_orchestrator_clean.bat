@echo off
echo ========================================
echo RIVO Orchestrator (Clean Windows Runner)
echo ========================================

REM Move to repo root (this file location)
cd /d %~dp0

REM Activate virtual environment
call .venv\Scripts\activate

REM Ensure PYTHONPATH is project root
set PYTHONPATH=%CD%

REM Run orchestrator
python app\orchestrator.py

pause
