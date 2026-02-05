@echo off
setlocal

REM Change to the folder where this .bat file is located (project root)
cd /d "%~dp0"

REM Activate virtual environment if it exists
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
)

REM Run orchestrator and pass through any arguments
python app\orchestrator.py %*

endlocal
