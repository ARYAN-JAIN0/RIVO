@echo off
REM Change to the folder where the .bat file is located
cd /d "%~dp0"
cd ..

REM Activate virtual environment if it exists
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
)

REM Run orchestrator
python app\orchestrator.py %*
```

**Translation:**
- `%~dp0` = The folder containing the .bat file
- `cd ..` = Go up one level to project root
- `%*` = Pass any arguments you provide

---

## 🎯 Different Ways to Use It

### Method 1: Double-Click (GUI)
```
1. Open Windows Explorer
2. Navigate to C:\Users\aryan\RIVO
3. Double-click run_orchestrator.bat
4. Window will open showing the pipeline execution