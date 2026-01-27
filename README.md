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

Install dependencies:
```bash
pip install -r requirements.txt
```

Run with Docker Compose:
```bash
docker-compose up
```
