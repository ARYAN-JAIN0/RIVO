
import sqlite3
from pathlib import Path

# Connect to the database
# Using relative path assuming script run from project root or scripts/ dir
DB_PATH = Path("rivo.db").resolve()
if not DB_PATH.exists():
    # Try finding it in parent directory
    DB_PATH = Path("../rivo.db").resolve()

print(f"Connecting to database at: {DB_PATH}")
conn = sqlite3.connect(str(DB_PATH))
cursor = conn.cursor()

try:
    # Check if column exists
    cursor.execute("PRAGMA table_info(leads)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if "signal_score" not in columns:
        print("Adding 'signal_score' column to 'leads' table...")
        cursor.execute("ALTER TABLE leads ADD COLUMN signal_score INTEGER")
        conn.commit()
        print("Column added successfully.")
    else:
        print("'signal_score' column already exists.")

except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
