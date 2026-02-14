# Entry point (later FastAPI)
from pathlib import Path
import sys

# Ensure project root is importable when running `python app/main.py`
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = str(Path(__file__).resolve().parent)
project_root_str = str(PROJECT_ROOT)
if SCRIPT_DIR in sys.path:
    sys.path.remove(SCRIPT_DIR)
if project_root_str in sys.path:
    sys.path.remove(project_root_str)
sys.path.insert(0, project_root_str)

from app.agents.sdr_agent import run_sdr_agent
from app.core.startup import bootstrap

if __name__ == "__main__":
    bootstrap()
    run_sdr_agent()
