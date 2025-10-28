import os
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import argparse

# SQLite database configuration
DB_PATH = "broken_links.db"
TEMP_DATA_DIR = "temp-data-links"

# Function to load CSV files from a directory and merge into the database
def load_csv_to_db(csv_files, db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Ensure the table exists
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS broken_links (
            Timestamp TEXT,
            URL TEXT,
            Status INTEGER,
            Path TEXT,
            Visible TEXT
        )
        """
    )

    # Load each CSV file into the database
    for csv_file in csv_files:
        print(f"Loading {csv_file} into database...")
        df = pd.read_csv(csv_file)
        df.to_sql("broken_links", conn, if_exists="append", index=False)

    conn.commit()
    conn.close()

# Function to enforce 60-day data retention
def enforce_retention(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Calculate the cutoff date
    cutoff_date = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d %H:%M:%S")

    # Delete old records
    cursor.execute("DELETE FROM broken_links WHERE Timestamp < ?", (cutoff_date,))
    conn.commit()
    conn.close()

# Function to query changes data grouped by date
def fetch_changes_data(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT date, COUNT(*) FROM broken_links GROUP BY date")
    data = cursor.fetchall()
    conn.close()
    return data

if __name__ == "__main__":
    print("Loading past data into the database...")
    load_csv_to_db(TEMP_DATA_DIR, DB_PATH)

    print("Enforcing 60-day data retention policy...")
    enforce_retention(DB_PATH)

    print("✅ Database updated successfully!")

    # Example usage
    db_path = "broken_links.db"
    changes_data = fetch_changes_data(db_path)
    print("Changes Data:", changes_data)