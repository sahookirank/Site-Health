import requests
import sqlite3
import json
import os
from datetime import datetime

def create_optimizely_flags_table(db_path='optimizely_flags.db'):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute('''
    CREATE TABLE IF NOT EXISTS optimizely_flags (
        id INTEGER PRIMARY KEY,
        flag_id INTEGER NOT NULL,
        flag_name TEXT NOT NULL,
        first_seen TEXT NOT NULL,
        updated_time TEXT
    )
    ''')
    conn.commit()
    conn.close()

def get_existing_flag_ids(db_path='optimizely_flags.db'):
    def get_all_flag_names(db_path='optimizely_flags.db'):
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute('SELECT flag_name FROM optimizely_flags')
        rows = cur.fetchall()
        conn.close()
        return [row[0] for row in rows]

    def fetch_flag_details(flag_name):
        url = f"https://api.app.optimizely.com/flags/projects/17801440189/flags/{flag_name}"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Failed to fetch details for flag {flag_name}: {response.status_code}")
                return None
        except Exception as e:
            print(f"Error fetching flag details for {flag_name}: {e}")
            return None

    def update_flag_details_in_db(flag_name, details, db_path='optimizely_flags.db'):
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        updated_time = details.get('updated_time', None)
        cur.execute('UPDATE optimizely_flags SET updated_time=? WHERE flag_name=?', (updated_time, flag_name))
        conn.commit()
        conn.close()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute('SELECT flag_id FROM optimizely_flags')
    rows = cur.fetchall()
    conn.close()
    return set(row[0] for row in rows)

def insert_new_flags(flags, db_path='optimizely_flags.db'):
    create_optimizely_flags_table(db_path)
    existing_ids = get_existing_flag_ids(db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    new_flags = [(f['id'], f['name'], datetime.utcnow().isoformat() + 'Z', f.get('updated_time', None)) for f in flags if f['id'] not in existing_ids]
    cur.executemany('INSERT INTO optimizely_flags (flag_id, flag_name, first_seen, updated_time) VALUES (?, ?, ?, ?)', new_flags)
    conn.commit()
    conn.close()
    return new_flags

def load_flags_from_json(json_path):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data['items']

def main():
        # Fetch and update details for all flags
        flag_names = get_all_flag_names(db_path)
        for flag_name in flag_names:
            details = fetch_flag_details(flag_name)
            if details:
                update_flag_details_in_db(flag_name, details, db_path)
    json_path = 'kmart.json'
    db_path = 'optimizely_flags.db'
    flags = load_flags_from_json(json_path)
    new_flags = insert_new_flags(flags, db_path)
    if new_flags:
        print(f"Added {len(new_flags)} new flags:")
        for flag in new_flags:
            print(f"  ID: {flag[0]}, Name: {flag[1]}")
    else:
        print("No new flags found.")

if __name__ == '__main__':
    main()
