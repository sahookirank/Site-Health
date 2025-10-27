#!/usr/bin/env python3
"""Enforce 60-day retention policy on broken_links.db historical tables."""

import os
import sqlite3
from datetime import date, timedelta, datetime

db_path = 'broken_links.db'
if not os.path.exists(db_path):
    raise SystemExit('broken_links.db not found; skipping retention enforcement')

conn = sqlite3.connect(db_path)
cur = conn.cursor()
cutoff = date.today() - timedelta(days=60)

cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'broken_links_%'")
tables = [row[0] for row in cur.fetchall()]

dropped = 0
for table in tables:
    suffix = table.replace('broken_links_', '')
    try:
        table_date = datetime.strptime(suffix, '%Y_%m_%d').date()
    except ValueError:
        continue
    if table_date < cutoff:
        print(f"Dropping historical table {table} older than 60 days")
        cur.execute(f"DROP TABLE IF EXISTS {table}")
        dropped += 1

conn.commit()
conn.close()
print(f"Retention enforcement complete; dropped {dropped} tables")
