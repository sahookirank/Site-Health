#!/usr/bin/env python3
"""
Screenshot Database Management
Standalone utilities for managing screenshot database
"""

import argparse
import os
from datetime import datetime, timedelta
from screenshot_database import ScreenshotDatabase

def cleanup_database(db_path='screenshots.db', keep_days=30):
    """Clean up old screenshots from database"""
    print(f"🧹 Cleaning up screenshots older than {keep_days} days...")

    db = ScreenshotDatabase(db_path)
    deleted_count = db.cleanup_old_screenshots(keep_days)

    print(f"✅ Cleanup complete: {deleted_count} old screenshots removed")

def show_database_stats(db_path='screenshots.db'):
    """Show database statistics"""
    db = ScreenshotDatabase(db_path)

    available_dates = db.get_available_dates()
    min_date, max_date = db.get_date_range()

    print("📊 Screenshot Database Statistics")
    print("=" * 40)
    print(f"📅 Available dates: {len(available_dates)}")
    print(f"📆 Date range: {min_date} to {max_date}")
    print(f"📄 Total screenshots: {len(available_dates)}")

    if available_dates:
        print(f"\n📋 Dates with screenshots:")
        for date in available_dates[:10]:  # Show first 10 dates
            screenshots = db.get_all_screenshots_for_date(date)
            print(f"  📅 {date}: {len(screenshots)} screenshots")

        if len(available_dates) > 10:
            print(f"  ... and {len(available_dates) - 10} more dates")

def export_screenshots_to_files(db_path='screenshots.db', output_dir='exported_screenshots'):
    """Export all screenshots from database to files"""
    import base64

    db = ScreenshotDatabase(db_path)
    available_dates = db.get_available_dates()

    print(f"📤 Exporting screenshots to {output_dir}/...")

    os.makedirs(output_dir, exist_ok=True)

    exported_count = 0
    for date in available_dates:
        screenshots = db.get_all_screenshots_for_date(date)

        date_dir = os.path.join(output_dir, date)
        os.makedirs(date_dir, exist_ok=True)

        for screenshot in screenshots:
            filepath = os.path.join(date_dir, screenshot['filename'])
            with open(filepath, 'wb') as f:
                f.write(screenshot['image_data'])
            exported_count += 1

    print(f"✅ Exported {exported_count} screenshots to {output_dir}/")

def main():
    parser = argparse.ArgumentParser(description='Screenshot Database Management')
    parser.add_argument('--db-path', default='screenshots.db', help='Path to screenshot database')
    parser.add_argument('--cleanup', type=int, help='Clean up screenshots older than N days')
    parser.add_argument('--stats', action='store_true', help='Show database statistics')
    parser.add_argument('--export', help='Export all screenshots to directory')

    args = parser.parse_args()

    if args.cleanup:
        cleanup_database(args.db_path, args.cleanup)
    elif args.stats:
        show_database_stats(args.db_path)
    elif args.export:
        export_screenshots_to_files(args.db_path, args.export)
    else:
        print("📋 Screenshot Database Management Tool")
        print("\nUsage:")
        print("  python3 screenshot_db_manager.py --stats          # Show database statistics")
        print("  python3 screenshot_db_manager.py --cleanup 30     # Clean up screenshots older than 30 days")
        print("  python3 screenshot_db_manager.py --export ./out   # Export all screenshots to ./out directory")

        # Show basic stats anyway
        show_database_stats(args.db_path)

if __name__ == "__main__":
    main()
