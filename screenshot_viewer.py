#!/usr/bin/env python3
"""
Standalone Screenshot Viewer
View and compare screenshots from the database independently of the main dashboard
"""

import argparse
import os
from datetime import datetime, timedelta
from screenshot_database import ScreenshotDatabase, get_image_data_url

def generate_standalone_viewer(db_path='screenshots.db', output_path='screenshot_viewer.html'):
    """Generate a standalone HTML viewer for screenshots"""

    # Initialize database
    db = ScreenshotDatabase(db_path)

    # Get available dates
    available_dates = db.get_available_dates()
    min_date, max_date = db.get_date_range()

    # Default dates
    today = datetime.now().strftime('%Y-%m-%d')
    yesterday = (datetime.now().date() - timedelta(days=1)).strftime('%Y-%m-%d')

    before_date = yesterday if yesterday in available_dates else (available_dates[-1] if available_dates else today)
    after_date = today

    # Fetch screenshots for both dates
    before_screenshots = db.get_all_screenshots_for_date(before_date)
    after_screenshots = db.get_all_screenshots_for_date(after_date)

    # Create lookup dictionaries
    before_lookup = {s['page_name']: s for s in before_screenshots}
    after_lookup = {s['page_name']: s for s in after_screenshots}

    # Get all unique page names
    all_pages = set(before_lookup.keys()) | set(after_lookup.keys())
    all_pages = sorted(all_pages)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kmart Screenshots - Database Viewer</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            line-height: 1.6;
            max-width: 1600px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f8fafc;
        }}
        .header {{
            background: linear-gradient(135deg, #e31837, #c4142b);
            color: white;
            padding: 20px;
            border-radius: 12px;
            text-align: center;
            margin-bottom: 30px;
        }}
        .comparison-container {{
            display: flex;
            gap: 20px;
            margin-bottom: 20px;
        }}
        .date-column {{
            flex: 1;
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .date-header {{
            background: linear-gradient(135deg, #1e40af, #3b82f6);
            color: white;
            padding: 20px;
            text-align: center;
            font-weight: bold;
            font-size: 20px;
        }}
        .date-selector {{
            padding: 20px;
            background: #f8fafc;
            border-bottom: 1px solid #e2e8f0;
        }}
        .date-selector label {{
            display: block;
            margin-bottom: 10px;
            font-weight: 600;
            color: #374151;
        }}
        .date-selector select {{
            width: 100%;
            padding: 12px;
            border: 2px solid #d1d5db;
            border-radius: 8px;
            font-size: 14px;
            background: white;
        }}
        .screenshot-item {{
            margin: 20px;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            overflow: hidden;
            background: white;
            transition: all 0.2s ease;
        }}
        .screenshot-item:hover {{
            box-shadow: 0 8px 25px rgba(0,0,0,0.15);
            transform: translateY(-2px);
        }}
        .screenshot-header {{
            padding: 16px;
            background: linear-gradient(135deg, #f8fafc, #f1f5f9);
            border-bottom: 1px solid #e2e8f0;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .page-name {{
            font-weight: 700;
            color: #1f2937;
            font-size: 16px;
        }}
        .status-badge {{
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
        }}
        .status-success {{
            background: #dcfce7;
            color: #166534;
            border: 1px solid #86efac;
        }}
        .status-error {{
            background: #fef2f2;
            color: #991b1b;
            border: 1px solid #fca5a5;
        }}
        .screenshot-image {{
            width: 100%;
            height: auto;
            display: block;
            border-top: 1px solid #e2e8f0;
        }}
        .no-screenshot {{
            padding: 60px 20px;
            text-align: center;
            color: #6b7280;
            background: #f9fafb;
            border: 2px dashed #d1d5db;
            margin: 20px;
            border-radius: 12px;
            font-style: italic;
        }}
        .comparison-info {{
            text-align: center;
            margin: 20px 0;
            padding: 20px;
            background: linear-gradient(135deg, #e0f2fe, #bae6fd);
            border-radius: 12px;
            color: #0c4a6e;
            border: 1px solid #7dd3fc;
        }}
        .stats {{
            display: flex;
            justify-content: center;
            gap: 20px;
            margin: 20px 0;
            flex-wrap: wrap;
        }}
        .stat-card {{
            background: white;
            padding: 15px 20px;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            text-align: center;
            min-width: 150px;
        }}
        .stat-value {{
            font-size: 24px;
            font-weight: bold;
            color: #e31837;
        }}
        .stat-label {{
            font-size: 12px;
            color: #6b7280;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-top: 5px;
        }}
        @media (max-width: 768px) {{
            .comparison-container {{
                flex-direction: column;
            }}
            .stats {{
                flex-direction: column;
                align-items: center;
            }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📸 Kmart Website Screenshots</h1>
        <p>Visual monitoring with database storage and historical comparison</p>
    </div>

    <div class="stats">
        <div class="stat-card">
            <div class="stat-value">{len(available_dates)}</div>
            <div class="stat-label">Available Dates</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{len(before_screenshots)}</div>
            <div class="stat-label">Before Screenshots</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{len(after_screenshots)}</div>
            <div class="stat-label">After Screenshots</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{len(all_pages)}</div>
            <div class="stat-label">Total Pages</div>
        </div>
    </div>

    <div class="comparison-info">
        <strong>📊 Database Comparison Mode</strong><br>
        Compare website screenshots across different dates. Select dates above to view visual changes over time.
        {'<br><strong>📅 Date Range:</strong> ' + min_date + ' to ' + max_date if min_date and max_date else ''}
    </div>

    <div class="comparison-container">
        <!-- Before Date Column -->
        <div class="date-column">
            <div class="date-header">Before ({before_date})</div>
            <div class="date-selector">
                <label for="beforeDateSelect">Select Date:</label>
                <select id="beforeDateSelect" onchange="updateComparison()">
                    {"".join(f'<option value="{date}" {"selected" if date == before_date else ""}>{date}</option>' for date in available_dates)}
                </select>
            </div>"""

    # Generate screenshot items for before date
    for page_name in all_pages:
        before_shot = before_lookup.get(page_name)

        html_content += f'''
            <div class="screenshot-item">
                <div class="screenshot-header">
                    <span class="page-name">{page_name.replace('-', ' ').title()}</span>
                    <span class="status-badge {'status-success' if before_shot else 'status-error'}">
                        {'✓ Available' if before_shot else '✗ Missing'}
                    </span>
                </div>'''

        if before_shot:
            image_data_url = get_image_data_url(before_shot['image_data'], before_shot['filename'])
            html_content += f'''
                <img src="{image_data_url}"
                     alt="Screenshot of {before_shot['url']} on {before_date}"
                     class="screenshot-image"
                     loading="lazy">'''
        else:
            html_content += '''
                <div class="no-screenshot">
                    No screenshot available for this page on the selected date
                </div>'''

        html_content += '''
            </div>'''

    html_content += '''
        </div>

        <!-- After Date Column -->
        <div class="date-column">
            <div class="date-header">After ({after_date})</div>
            <div class="date-selector">
                <label for="afterDateSelect">Select Date:</label>
                <select id="afterDateSelect" onchange="updateComparison()">
                    {"".join(f'<option value="{date}" {"selected" if date == after_date else ""}>{date}</option>' for date in available_dates)}
                </select>
            </div>'''

    # Generate screenshot items for after date
    for page_name in all_pages:
        after_shot = after_lookup.get(page_name)

        html_content += f'''
            <div class="screenshot-item">
                <div class="screenshot-header">
                    <span class="page-name">{page_name.replace('-', ' ').title()}</span>
                    <span class="status-badge {'status-success' if after_shot else 'status-error'}">
                        {'✓ Available' if after_shot else '✗ Missing'}
                    </span>
                </div>'''

        if after_shot:
            image_data_url = get_image_data_url(after_shot['image_data'], after_shot['filename'])
            html_content += f'''
                <img src="{image_data_url}"
                     alt="Screenshot of {after_shot['url']} on {after_date}"
                     class="screenshot-image"
                     loading="lazy">'''
        else:
            html_content += '''
                <div class="no-screenshot">
                    No screenshot available for this page on the selected date
                </div>'''

        html_content += '''
            </div>'''

    html_content += '''
        </div>
    </div>

    <script>
        function updateComparison() {
            const beforeDate = document.getElementById('beforeDateSelect').value;
            const afterDate = document.getElementById('afterDateSelect').value;

            // Update URL parameters to reflect date selection
            const url = new URL(window.location);
            url.searchParams.set('before', beforeDate);
            url.searchParams.set('after', afterDate);
            window.location.href = url.toString();
        }

        // Auto-reload if URL parameters change (for bookmarking)
        window.addEventListener('load', function() {
            const urlParams = new URLSearchParams(window.location.search);
            const beforeParam = urlParams.get('before');
            const afterParam = urlParams.get('after');

            if (beforeParam) {
                document.getElementById('beforeDateSelect').value = beforeParam;
            }
            if (afterParam) {
                document.getElementById('afterDateSelect').value = afterParam;
            }
        });

        // Add some interactivity
        document.addEventListener('DOMContentLoaded', function() {
            console.log('Screenshot viewer loaded');
            console.log('Available dates:', {len(available_dates)});
            console.log('Before date:', '{before_date}');
            console.log('After date:', '{after_date}');
        });
    </script>
</body>
</html>'''

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"✅ Generated standalone screenshot viewer: {output_path}")
    print(f"   Available dates: {len(available_dates)}")
    print(f"   Date range: {min_date} to {max_date}")
    print(f"   Pages tracked: {len(all_pages)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate standalone screenshot viewer')
    parser.add_argument('--db-path', default='screenshots.db', help='Path to screenshot database')
    parser.add_argument('--output', default='screenshot_viewer.html', help='Output HTML file path')
    args = parser.parse_args()

    generate_standalone_viewer(args.db_path, args.output)
