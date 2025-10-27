#!/usr/bin/env python3
"""
Screenshot Database Manager
Handles storage and retrieval of screenshots with date-based comparison functionality
"""

import sqlite3
import os
import json
from datetime import datetime, date, timedelta
from pathlib import Path

class ScreenshotDatabase:
    def __init__(self, db_path='screenshots.db'):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Initialize the database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create screenshots table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS screenshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                page_name TEXT NOT NULL,
                url TEXT NOT NULL,
                filename TEXT NOT NULL,
                image_data BLOB,
                metadata TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(date, page_name)
            )
        ''')

        # Create indexes for better performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_date ON screenshots(date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_page_name ON screenshots(page_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_date_page ON screenshots(date, page_name)')

        conn.commit()
        conn.close()
        print(f"✅ Screenshot database initialized: {self.db_path}")

    def store_screenshot(self, page_name, url, filename, image_data, metadata=None, screenshot_date=None):
        """Store a screenshot in the database"""
        if screenshot_date is None:
            screenshot_date = date.today().strftime('%Y-%m-%d')

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT OR REPLACE INTO screenshots
                (date, page_name, url, filename, image_data, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (screenshot_date, page_name, url, filename, image_data, json.dumps(metadata) if metadata else None))

            conn.commit()
            print(f"✅ Stored screenshot: {page_name} for {screenshot_date}")
            return True

        except Exception as e:
            print(f"❌ Error storing screenshot {page_name}: {str(e)}")
            return False

        finally:
            conn.close()

    def get_screenshot_by_date_and_page(self, screenshot_date, page_name):
        """Get a specific screenshot by date and page name"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT id, page_name, url, filename, image_data, metadata, created_at
                FROM screenshots
                WHERE date = ? AND page_name = ?
            ''', (screenshot_date, page_name))

            row = cursor.fetchone()
            if row:
                return {
                    'id': row[0],
                    'page_name': row[1],
                    'url': row[2],
                    'filename': row[3],
                    'image_data': row[4],
                    'metadata': json.loads(row[5]) if row[5] else None,
                    'created_at': row[6]
                }
            return None

        finally:
            conn.close()

    def get_all_screenshots_for_date(self, screenshot_date):
        """Get all screenshots for a specific date"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT page_name, url, filename, image_data, metadata, created_at
                FROM screenshots
                WHERE date = ?
                ORDER BY page_name
            ''', (screenshot_date,))

            results = []
            for row in cursor.fetchall():
                results.append({
                    'page_name': row[0],
                    'url': row[1],
                    'filename': row[2],
                    'image_data': row[3],
                    'metadata': json.loads(row[4]) if row[4] else None,
                    'created_at': row[5]
                })

            return results

        finally:
            conn.close()

    def get_available_dates(self):
        """Get all dates that have screenshots"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT DISTINCT date
                FROM screenshots
                ORDER BY date DESC
            ''')

            dates = [row[0] for row in cursor.fetchall()]
            return dates

        finally:
            conn.close()

    def get_date_range(self):
        """Get the date range of available screenshots"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT MIN(date), MAX(date)
                FROM screenshots
            ''')

            row = cursor.fetchone()
            if row and row[0] and row[1]:
                return row[0], row[1]
            return None, None

        finally:
            conn.close()

    def delete_screenshots_for_date(self, screenshot_date):
        """Delete all screenshots for a specific date"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute('DELETE FROM screenshots WHERE date = ?', (screenshot_date,))
            deleted_count = cursor.rowcount
            conn.commit()
            print(f"🗑️ Deleted {deleted_count} screenshots for {screenshot_date}")
            return deleted_count

        finally:
            conn.close()

    def cleanup_old_screenshots(self, keep_days=30):
        """Clean up screenshots older than specified days"""
        cutoff_date = (date.today() - timedelta(days=keep_days)).strftime('%Y-%m-%d')

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute('DELETE FROM screenshots WHERE date < ?', (cutoff_date,))
            deleted_count = cursor.rowcount
            conn.commit()

            if deleted_count > 0:
                print(f"🧹 Cleaned up {deleted_count} old screenshots (before {cutoff_date})")

            return deleted_count

        finally:
            conn.close()

def save_screenshot_to_db(screenshot_db, page_name, url, filename, image_path, metadata=None):
    """Helper function to save a screenshot file to database"""
    try:
        with open(image_path, 'rb') as f:
            image_data = f.read()

        success = screenshot_db.store_screenshot(page_name, url, filename, image_data, metadata)
        return success

    except Exception as e:
        print(f"❌ Error reading screenshot file {image_path}: {str(e)}")
        return False

def get_image_data_url(image_data, filename):
    """Convert binary image data to data URL for HTML display"""
    import base64

    # Determine MIME type based on filename
    if filename.lower().endswith('.jpg') or filename.lower().endswith('.jpeg'):
        mime_type = 'image/jpeg'
    elif filename.lower().endswith('.png'):
        mime_type = 'image/png'
    else:
        mime_type = 'image/jpeg'  # default

    # Convert to base64
    image_b64 = base64.b64encode(image_data).decode('utf-8')
    return f"data:{mime_type};base64,{image_b64}"
