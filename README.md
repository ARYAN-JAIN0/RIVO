# RIVO Project

## Project Structure

- **app/**: Application layer
  - `main.py` - Entry point (later FastAPI)
  - `config.py` - Environment variables

- **agents/**: Intelligence layer
  - `sdr_agent.py`
  - `sales_agent.py`
  - `negotiation_agent.py`
  - `finance_agent.py`

- **memory/**: Memory storage
  - `vector_store.py` - ChromaDB
  - `graph_store.py` - NetworkX

- **services/**: External actions
  - `email_sender.py`
  - `invoice_generator.py`

- **db/**: Database layer
  - `db_handler.py`
  - `schema.sql`

- **ui/**: User interface
  - `dashboard.py` - Streamlit

- **workers/**: Background jobs
  - `scheduler.py` - Celery / cron jobs

- **tests/**: Test suite

## Setup

### 1) Clone and enter the repo

```bash
git clone <your-repo-url>
cd RIVO
```

### 2) Create and activate a virtual environment (recommended)

```bash
python -m venv .venv
source .venv/bin/activate      # macOS/Linux
# .venv\Scripts\activate      # Windows PowerShell
```

### 3) Install dependencies

```bash
pip install -r requirements.txt
```

## How to run the project

This repo currently has three practical run modes:

### A) Run the SDR pipeline from CLI

```bash
python app/main.py
```

`app/main.py` calls `run_sdr_agent()` and processes leads using the CSV files in `db/`.

### B) Run the single-agent review dashboard (Streamlit)

```bash
streamlit run ui/dashboard.py
```

### C) Run the multi-agent review dashboard (Streamlit)

```bash
streamlit run app/multi_agent_dashboard.py
```

Then open the local URL Streamlit prints in the terminal (usually `http://localhost:8501`).

### D) Run the orchestrator on Windows (`run_orchestrator.bat`)

From **Command Prompt** in the project root:

```bat
run_orchestrator.bat
```

Or run a specific stage:

```bat
run_orchestrator.bat sdr
run_orchestrator.bat sales
run_orchestrator.bat negotiation
run_orchestrator.bat finance
run_orchestrator.bat health
```

You can also double-click `run_orchestrator.bat` in File Explorer to run the full pipeline.

## Docker Compose status

A `docker-compose.yml` file exists, but it is currently a placeholder and does not yet define runnable services. For now, use the Python/Streamlit commands above.

## Create a **new GitHub repo** with the **full commit history**

If you want to move this code to a new repo while preserving all commits:

### Option 1: Keep this local repo and switch remote

```bash
# From inside this repo
git remote -v

# Remove old origin if it exists
git remote remove origin

# Add your new GitHub repo URL
git remote add origin https://github.com/<your-user>/<new-repo>.git

# Push the current branch and all history
git push -u origin work

# Push all local branches and tags as well (optional but recommended)
git push --all origin
git push --tags origin
```

### Option 2: Mirror push everything (branches + tags + refs)

```bash
# From a fresh clone of the old repo
git clone --mirror <old-repo-url>
cd <old-repo-name>.git

git remote set-url origin https://github.com/<your-user>/<new-repo>.git
git push --mirror
```

Use Option 2 when you want an exact full-fidelity migration.
