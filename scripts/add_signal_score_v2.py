
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import text, inspect
from app.database.db import engine

def add_column():
    print(f"Connecting to database: {engine.url}")
    
    with engine.connect() as conn:
        inspector = inspect(conn)
        columns = [col['name'] for col in inspector.get_columns('leads')]
        
        if 'signal_score' in columns:
            print("Column 'signal_score' already exists in 'leads' table.")
        else:
            print("Adding 'signal_score' column to 'leads' table...")
            try:
                # PostgreSQL and SQLite support ADD COLUMN syntax
                conn.execute(text("ALTER TABLE leads ADD COLUMN signal_score INTEGER"))
                conn.commit()
                print("Column added successfully.")
            except Exception as e:
                print(f"Error adding column: {e}")

if __name__ == "__main__":
    add_column()
