import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import os

def create_database_tables(conn, date_str):
    """Create table for a specific date"""
    table_name = f"broken_links_{date_str.replace('-', '_')}"
    cursor = conn.cursor()
    
    # Drop existing table if it exists
    cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
    
    # Create new table
    cursor.execute(f'''
        CREATE TABLE {table_name} (
            Region TEXT,
            URL TEXT,
            Status INTEGER,
            Response_Time REAL,
            Error_Message TEXT,
            Timestamp TEXT,
            PRIMARY KEY (Region, URL)
        )
    ''')
    conn.commit()
    return table_name

def load_broken_links_from_csv(csv_path, region):
    """Load broken links (non-200 status) from CSV file"""
    if not os.path.exists(csv_path):
        print(f"Warning: {csv_path} not found")
        return pd.DataFrame()
    
    df = pd.read_csv(csv_path)
    print(f"Loaded {len(df)} total links from {csv_path}")
    
    # Clean data: remove rows with NaN status and convert to numeric
    df = df.dropna(subset=['Status'])
    df['Status'] = pd.to_numeric(df['Status'], errors='coerce')
    df = df.dropna(subset=['Status'])  # Remove any that couldn't be converted
    
    # Filter broken links (non-200 status)
    broken_df = df[df['Status'] != 200].copy()
    broken_df['Region'] = region
    
    print(f"Found {len(broken_df)} broken links for {region}")
    return broken_df

def insert_broken_links_to_db(conn, table_name, broken_df, timestamp):
    """Insert broken links into database table"""
    cursor = conn.cursor()
    
    for _, row in broken_df.iterrows():
        cursor.execute(f'''
            INSERT OR REPLACE INTO {table_name} 
            (Region, URL, Status, Response_Time, Error_Message, Timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            row['Region'],
            row['URL'],
            int(row['Status']),
            row.get('Response_Time', 0.0),
            row.get('Error_Message', ''),
            timestamp
        ))
    
    conn.commit()
    print(f"Inserted {len(broken_df)} broken links into {table_name}")

def compare_broken_links(conn, date1, date2):
    """Compare broken links between two dates"""
    table1 = f"broken_links_{date1.replace('-', '_')}"
    table2 = f"broken_links_{date2.replace('-', '_')}"
    
    cursor = conn.cursor()
    
    # Get broken links for both dates
    try:
        cursor.execute(f"SELECT Region, URL, Status FROM {table1}")
        links1 = set((row[0], row[1]) for row in cursor.fetchall())
        
        cursor.execute(f"SELECT Region, URL, Status FROM {table2}")
        links2 = set((row[0], row[1]) for row in cursor.fetchall())
        
        # Calculate differences
        added_links = links2 - links1
        removed_links = links1 - links2
        
        print(f"\n=== Comparison between {date1} and {date2} ===")
        print(f"{date1}: {len(links1)} broken links")
        print(f"{date2}: {len(links2)} broken links")
        print(f"Added: {len(added_links)} links")
        print(f"Removed: {len(removed_links)} links")
        
        if added_links:
            print("\nAdded broken links:")
            for region, url in sorted(added_links):
                cursor.execute(f"SELECT Status FROM {table2} WHERE Region=? AND URL=?", (region, url))
                status = cursor.fetchone()[0]
                print(f"  {region}: {url} (Status: {status})")
        
        if removed_links:
            print("\nRemoved broken links (fixed):")
            for region, url in sorted(removed_links):
                cursor.execute(f"SELECT Status FROM {table1} WHERE Region=? AND URL=?", (region, url))
                status = cursor.fetchone()[0]
                print(f"  {region}: {url} (Status: {status})")
                
        return {
            'date1': date1,
            'date2': date2,
            'count1': len(links1),
            'count2': len(links2),
            'added': list(added_links),
            'removed': list(removed_links)
        }
        
    except sqlite3.OperationalError as e:
        print(f"Error comparing dates: {e}")
        return None

def update_changes_csv(comparison_data):
    """Update changes_all.csv with comparison results"""
    changes_data = []
    
    # Add removed links
    for region, url in comparison_data['removed']:
        changes_data.append({
            'Region': region,
            'URL': url,
            'Change': 'Removed',
            'Window': 'Yesterday'
        })
    
    # Add added links
    for region, url in comparison_data['added']:
        changes_data.append({
            'Region': region,
            'URL': url,
            'Change': 'Added',
            'Window': 'Today'
        })
    
    if changes_data:
        changes_df = pd.DataFrame(changes_data)
        changes_df.to_csv('changes_all.csv', index=False)
        print(f"\nUpdated changes_all.csv with {len(changes_data)} changes")
    else:
        print("\nNo changes to write to changes_all.csv")

def main():
    # Connect to database
    conn = sqlite3.connect('broken_links.db')
    
    # Define dates (using current date as today, yesterday as previous day)
    today = datetime.now().strftime('%Y-%m-%d')
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    print(f"Processing data for {yesterday} and {today}")
    
    # Process yesterday's data (2025-08-24)
    yesterday_date = '2025-08-24'
    print(f"\n=== Processing {yesterday_date} ===")
    
    # Create table for yesterday
    yesterday_table = create_database_tables(conn, yesterday_date)
    
    # Load broken links from temp CSV files
    au_broken_yesterday = load_broken_links_from_csv('temp/au_link_check_results.csv', 'AU')
    nz_broken_yesterday = load_broken_links_from_csv('temp/nz_link_check_results.csv', 'NZ')
    
    # Combine and insert yesterday's data
    yesterday_combined = pd.concat([au_broken_yesterday, nz_broken_yesterday], ignore_index=True)
    if not yesterday_combined.empty:
        insert_broken_links_to_db(conn, yesterday_table, yesterday_combined, yesterday_date)
    
    # Process today's data (2025-08-25) - using smaller CSV files as current data
    today_date = '2025-08-25'
    print(f"\n=== Processing {today_date} ===")
    
    # Create table for today
    today_table = create_database_tables(conn, today_date)
    
    # Load broken links from current CSV files (smaller ones)
    au_broken_today = load_broken_links_from_csv('au_link_check_results.csv', 'AU')
    nz_broken_today = load_broken_links_from_csv('nz_link_check_results.csv', 'NZ')
    
    # Combine and insert today's data
    today_combined = pd.concat([au_broken_today, nz_broken_today], ignore_index=True)
    if not today_combined.empty:
        insert_broken_links_to_db(conn, today_table, today_combined, today_date)
    
    # Compare the two dates
    print(f"\n=== Comparing {yesterday_date} vs {today_date} ===")
    comparison = compare_broken_links(conn, yesterday_date, today_date)
    
    if comparison:
        # Update changes CSV
        update_changes_csv(comparison)
    
    # Show final summary
    cursor = conn.cursor()
    cursor.execute(f"SELECT COUNT(*) FROM {yesterday_table}")
    yesterday_count = cursor.fetchone()[0]
    
    cursor.execute(f"SELECT COUNT(*) FROM {today_table}")
    today_count = cursor.fetchone()[0]
    
    print(f"\n=== FINAL SUMMARY ===")
    print(f"Database now contains:")
    print(f"  {yesterday_date}: {yesterday_count} broken links")
    print(f"  {today_date}: {today_count} broken links")
    print(f"  Net change: {today_count - yesterday_count} links")
    
    conn.close()
    print("\nDatabase update completed successfully!")

if __name__ == "__main__":
    main()