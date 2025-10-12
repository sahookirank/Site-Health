#!/usr/bin/env python3
"""
Store daily New Relic PageView data in SQLite DB.

This script stores the JSON response from NRQL queries into a persistent SQLite DB,
with a table for daily data.
"""
import sqlite3
import json
import os
from datetime import datetime

def create_db():
    conn = sqlite3.connect('page_views_daily.db')
    cur = conn.cursor()
    cur.execute('''
    CREATE TABLE IF NOT EXISTS daily_page_views (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT UNIQUE,
        products_json TEXT,
        pages_json TEXT,
        generated_at TEXT
    )
    ''')
    conn.commit()
    conn.close()

def store_daily_data(date, products_json, pages_json):
    # Ensure the database and table exist
    create_db()
    
    conn = sqlite3.connect('page_views_daily.db')
    cur = conn.cursor()
    generated_at = datetime.utcnow().isoformat() + 'Z'
    cur.execute('''
    INSERT OR REPLACE INTO daily_page_views (date, products_json, pages_json, generated_at)
    VALUES (?, ?, ?, ?)
    ''', (date, json.dumps(products_json), json.dumps(pages_json), generated_at))
    conn.commit()
    conn.close()
    print(f"Stored data for {date}")

if __name__ == '__main__':
    create_db()