#!/usr/bin/env python3
"""
New Relic Top Products Data Processor
Generates HTML content for top product URLs and their page visit counts

Environment Variables:
- NEWRELIC_COOKIE: New Relic session cookie.
- NEWRELIC_BASE_URL: The complete metadata URL for the payload.
- NEWRELIC_ACCOUNT_ID: The New Relic account ID.

Usage:
  # Production (with cookie environment variable)
  export NEWRELIC_COOKIE="your_cookie"
  export NEWRELIC_BASE_URL="your_metadata_url"
  export NEWRELIC_ACCOUNT_ID="your_account_id"
  python newrelic_top_products.py

GitHub Workflow:
  The deploy-gh-pages.yml workflow uses repository secrets:
  - secrets.NEWRELIC_COOKIE
  - secrets.NEWRELIC_BASE_URL
  - secrets.NEWRELIC_ACCOUNT_ID
"""

import json
import requests
import os
from datetime import datetime
from urllib.parse import unquote
import csv
import pandas as pd
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from store_daily_data import store_daily_data

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("Warning: python-dotenv not installed. Install with: pip install python-dotenv")
    print("Continuing with existing environment variables...")

def get_dynamic_headers_and_payload():
    """
    Get headers and payload using cookie from environment variables.
    Returns None if environment variables are not set.
    """
    metadata_url = os.getenv('NEWRELIC_BASE_URL')
    cookie = os.getenv('NEWRELIC_COOKIE')
    account_id = os.getenv('NEWRELIC_ACCOUNT_ID')

    if not metadata_url or not account_id:
        print("Warning: New Relic environment variables not configured.")
        return None, None, None

    if not cookie:
        print("Warning: NEWRELIC_COOKIE environment variable not set. Requests may fail.")

    base_url = "https://chartdata.service.newrelic.com/v3/nrql?"  # API host

    # Build headers with all required fields
    headers = {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate, br',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Content-Type': 'application/json',
        'Referer': 'https://one.newrelic.com/',
        'sec-ch-ua': '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
        'x-query-source-capability-id': 'QUERY_BUILDER',
        'x-query-source-component': 'Billboard Visualization',
        'x-query-source-component-id': 'viz-billboard',
        'x-query-source-feature': 'Query your data',
        'x-query-source-feature-id': 'unified-data-exploration.home',
        'x-query-source-ui-package-id': 'viz',
        'x-requested-with': 'XMLHttpRequest',
        'newrelic-requesting-services': 'viz|nr1-ui',
    }
    
    if cookie:
        headers['Cookie'] = cookie
    
    # Build payload
    # Note: 'SINCE today' uses New Relic's account timezone (typically UTC)
    # This ensures we get data from the start of the current day (00:00:00)
    # rather than the last 24 hours which could include previous day's data
    payload = {
        "account_ids": [int(account_id)],
        "nrql": "SELECT count(*) FROM PageView WHERE pageUrl RLIKE '.*[0-9]+.*' FACET pageUrl ORDER BY count(*) SINCE today"
    }
    return headers, payload, base_url

def parse_response_data(response_data):
    """
    Parse the New Relic API response data to extract product data
    Handles both old nested dict format and new list format
    """
    products = []
    
    if not response_data:
        return products
    
    # Handle new list format (direct results)
    if isinstance(response_data, list) and len(response_data) > 0:
        # Check if this is the new nested structure with series
        first_item = response_data[0]
        if isinstance(first_item, dict) and 'series' in first_item:
            # Handle the nested series structure: response[0]['series'][0]['series']
            try:
                outer_series = first_item.get('series', [])
                if outer_series and len(outer_series) > 0:
                    inner_series = outer_series[0].get('series', [])
                    
                    for product in inner_series:
                        url = product.get('name', '').strip()
                        data = product.get('data', [])
                        
                        # Skip "Other" entries
                        if url and (url.lower() == 'other' or 'other' in url.lower()):
                            continue
                        
                        if data and len(data) > 0 and len(data[0]) > 1:
                            count = data[0][1]  # count is at index 1
                            begin_time = data[0][0]  # timestamp at index 0
                            
                            # Convert timestamp to readable date
                            try:
                                date_str = datetime.fromtimestamp(begin_time / 1000).strftime('%Y-%m-%d %H:%M:%S')
                            except:
                                date_str = 'Unknown'
                            
                            # Clean URL (remove backticks and extra spaces)
                            clean_url = url.strip('` ').strip()
                            
                            products.append({
                                'url': clean_url,
                                'count': count,
                                'timestamp': date_str
                            })
            except Exception as e:
                print(f"Error parsing nested series structure: {e}")
        else:
            # Handle simple list format
            for item in response_data:
                if isinstance(item, dict):
                    # Extract URL and count from facet results
                    url = item.get('facet', item.get('name', ''))
                    count = item.get('count', item.get('results', [{}])[0].get('count', 0))
                    
                    # Skip "Other" entries
                    if url and (url.lower() == 'other' or 'other' in url.lower()):
                        continue
                    
                    if url:  # Only add if we have a valid URL
                        products.append({
                            'url': url,
                            'count': count,
                            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        })
    
    # Handle old nested dict format (for backward compatibility)
    elif isinstance(response_data, dict):
        series_data = response_data.get('series', [])
        if series_data and len(series_data) > 0:
            product_series = series_data[0].get('series', [])
            
            for product in product_series:
                url = product.get('name', '')
                data = product.get('data', [])
                
                # Skip "Other" entries
                if url.lower() == 'other' or 'other' in url.lower():
                    continue
                
                if data and len(data) > 0:
                    count = data[0][1]  # count is at index 1
                    begin_time = data[0][0]  # timestamp at index 0
                    
                    # Convert timestamp to readable date
                    try:
                        date_str = datetime.fromtimestamp(begin_time / 1000).strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        date_str = 'Unknown'
                    
                    products.append({
                        'url': url,
                        'count': count,
                        'timestamp': date_str
                    })
    
    # Sort by count descending
    products.sort(key=lambda x: x['count'], reverse=True)
    return products

def generate_html_content(products):
    """
    Generate HTML content for the top products table
    """
    html_content = '''
                <div class="summary-container">
                    <span class="summary-item">📊 Total Products: {total_products}</span>
                    <span class="summary-item">🔥 Top Product Views: {top_views:,}</span>
                    <span class="summary-item">📈 Total Page Views: {total_views:,}</span>
                </div>
                
                <table id="topProductsTable" class="display" style="width:100%">
                    <thead>
                        <tr>
                            <th>Rank</th>
                            <th>Product URL</th>
                            <th>Page Views</th>
                            <th>Last Updated</th>
                        </tr>
                    </thead>
                    <tbody>
'''
    
    total_views = sum(p['count'] for p in products)
    top_views = products[0]['count'] if products else 0
    
    for i, product in enumerate(products, 1):
        # Extract product name from URL for better display
        url_parts = product['url'].split('/')
        product_name = url_parts[-2] if len(url_parts) > 1 else product['url']
        product_name = product_name.replace('-', ' ').title()
        
        # Sanitize URL and product name to ensure valid UTF-8
        safe_url = product['url'].encode('utf-8', 'ignore').decode('utf-8')
        safe_product_name = product_name.encode('utf-8', 'ignore').decode('utf-8')
        safe_timestamp = product['timestamp'].encode('utf-8', 'ignore').decode('utf-8')
        
        html_content += f'''
                        <tr class="table-row" style="display: none;">
                            <td>{i}</td>
                            <td>
                                <a href="{safe_url}" target="_blank" title="{safe_url}">
                                    {safe_product_name}
                                </a>
                                <br><small style="color: #666;">{safe_url}</small>
                            </td>
                            <td><strong>{product['count']:,}</strong></td>
                            <td>{safe_timestamp}</td>
                        </tr>
'''
    
    html_content += '''
                    </tbody>
                </table>
'''
    
    return html_content.format(
        total_products=len(products),
        top_views=top_views,
        total_views=total_views
    )

# ---------------- New helpers for Page Views container ----------------

def generate_top_pages_html(pages):
    html_content = '''
                <div class="summary-container">
                    <span class="summary-item">📊 Total Pages: {total_pages}</span>
                    <span class="summary-item">🔥 Top Page Views: {top_views:,}</span>
                    <span class="summary-item">📈 Total Page Views: {total_views:,}</span>
                </div>
                <table id="topPagesTable" class="display" style="width:100%">
                    <thead>
                        <tr>
                            <th>Rank</th>
                            <th>Page URL</th>
                            <th>Views</th>
                            <th>Last Updated</th>
                        </tr>
                    </thead>
                    <tbody>
'''
    total_views = sum(p['count'] for p in pages)
    top_views = pages[0]['count'] if pages else 0
    for i, page in enumerate(pages, 1):
        # Sanitize URL and timestamp to ensure valid UTF-8
        safe_url = page['url'].encode('utf-8', 'ignore').decode('utf-8')
        safe_timestamp = page['timestamp'].encode('utf-8', 'ignore').decode('utf-8')
        
        html_content += f'''
                        <tr class="table-row" style="display: none;">
                            <td>{i}</td>
                            <td><a href="{safe_url}" target="_blank">{safe_url}</a></td>
                            <td><strong>{page['count']:,}</strong></td>
                            <td>{safe_timestamp}</td>
                        </tr>
'''
    html_content += '''
                    </tbody>
                </table>
'''
    return html_content.format(total_pages=len(pages), top_views=top_views, total_views=total_views)


def generate_broken_links_views_html(items):
    html_content = '''
                <div class="summary-container">
                    <span class="summary-item">🔗 Broken Link URLs Tracked: {total_urls}</span>
                    <span class="summary-item">👁️‍🗨️ URLs With Views: {urls_with_views}</span>
                    <span class="summary-item">📈 Total Views (Sum): {total_views:,}</span>
                </div>
                <table id="brokenLinksViewsTable" class="display" style="width:100%">
                    <thead>
                        <tr>
                            <th>Rank</th>
                            <th>URL</th>
                            <th>Views (30d)</th>
                        </tr>
                    </thead>
                    <tbody>
'''
    sorted_items = sorted(items, key=lambda x: x['count'], reverse=True)
    total_views = sum(i['count'] for i in sorted_items)
    for i, it in enumerate(sorted_items, 1):
        # Sanitize URL to ensure valid UTF-8
        safe_url = it['url'].encode('utf-8', 'ignore').decode('utf-8')
        
        html_content += f'''
                        <tr class="table-row" style="display: none;">
                            <td>{i}</td>
                            <td><a href="{safe_url}" target="_blank">{safe_url}</a></td>
                            <td><strong>{it['count']:,}</strong></td>
                        </tr>
'''
    html_content += '''
                    </tbody>
                </table>
'''
    return html_content.format(
        total_urls=len(items),
        urls_with_views=sum(1 for i in items if i['count'] > 0),
        total_views=total_views,
    )


def build_page_views_container_html(top_products, top_pages, broken_links_views):
    """Compose the Page Views parent container with three sub-tabs"""
    return f'''
        <div id="PageViewsContainer" class="card">
            <div style="display:flex; gap:12px; padding:8px 0 0 0;">
                <button class="pv-tab-link active" onclick="openPvTab(event, 'PV_Top_Products')">Top Products</button>
                <button class="pv-tab-link" onclick="openPvTab(event, 'PV_Top_Pages')">Top Pages</button>
                <button class="pv-tab-link" onclick="openPvTab(event, 'PV_Broken_Links')">Broken Links Views</button>
            </div>
            <div id="PV_Top_Products" class="pv-tab-content" style="display:block;">{generate_html_content(top_products)}</div>
            <div id="PV_Top_Pages" class="pv-tab-content">{generate_top_pages_html(top_pages)}</div>
            <div id="PV_Broken_Links" class="pv-tab-content">{generate_broken_links_views_html(broken_links_views)}</div>
        </div>
        <style>
            .pv-tab-link {{
                background-color: #f3f4f6; border: 1px solid #e5e7eb; padding: 8px 16px; cursor: pointer; border-radius: 8px;
                font-weight: 600; font-size: 14px; letter-spacing: .2px; transition: all .15s ease;
            }}
            .pv-tab-link.active, .pv-tab-link:hover {{ background-color: #e9effe; border-color: #c2d3ff; color: #0b3fbf; }}
            .pv-tab-content {{ display:none; padding: 8px 0; max-height: 600px; overflow-y: auto; }}
        </style>
        <script>
            function openPvTab(evt, tabId) {{
                var container = document.getElementById('PageViewsContainer');
                var contents = container.getElementsByClassName('pv-tab-content');
                for (var i=0; i<contents.length; i++) {{ contents[i].style.display = 'none'; }}
                var links = container.getElementsByClassName('pv-tab-link');
                for (var j=0; j<links.length; j++) {{ links[j].className = links[j].className.replace(' active',''); }}
                document.getElementById(tabId).style.display = 'block';
                evt.currentTarget.className += ' active';
                
                // Initialize infinite scroll for the newly active tab
                initializeInfiniteScroll(tabId);
            }}
            
            function initializeInfiniteScroll(tabId) {{
                var tabContent = document.getElementById(tabId);
                var table = tabContent.querySelector('table');
                if (!table) return;
                
                var rows = table.querySelectorAll('.table-row');
                var visibleRows = 50; // Show 50 rows initially
                var increment = 50; // Load 50 more rows at a time
                
                // Show initial rows
                for (var i = 0; i < Math.min(visibleRows, rows.length); i++) {{
                    rows[i].style.display = '';
                }}
                
                // Add scroll listener to the tab content
                tabContent.addEventListener('scroll', function() {{
                    var scrollTop = tabContent.scrollTop;
                    var scrollHeight = tabContent.scrollHeight;
                    var clientHeight = tabContent.clientHeight;
                    
                    // Load more when scrolled near bottom (100px threshold)
                    if (scrollTop + clientHeight >= scrollHeight - 100 && visibleRows < rows.length) {{
                        var newVisibleRows = Math.min(visibleRows + increment, rows.length);
                        for (var i = visibleRows; i < newVisibleRows; i++) {{
                            rows[i].style.display = '';
                        }}
                        visibleRows = newVisibleRows;
                    }}
                }});
            }}
            
            // Initialize infinite scroll for the default active tab
            // Note: Now handled by main tab switching in report_generator.py
            // document.addEventListener('DOMContentLoaded', function() {{
            //     initializeInfiniteScroll('PV_Top_Products');
            // });
        </script>
    '''


def _fetch_nrql(headers, base_url, nrql):
    account_id = os.getenv('NEWRELIC_ACCOUNT_ID')
    payload = {
        "account_ids": [int(account_id)],
        "nrql": nrql
    }
    return make_api_request(headers, payload, base_url)


def _read_broken_links_urls(script_dir):
    """
    Read broken links URLs from AU and NZ link check results CSV files.
    Only includes URLs with Status >= 400 (broken links) that are actually shown in the AU and NZ tabs.
    """
    urls = set()
    # Read from the actual broken links CSV files that contain the data shown in AU and NZ tabs
    csv_files = [
        ('au_broken_links.csv', 'AU'),
        ('nz_broken_links.csv', 'NZ')
    ]
    
    for filename, region in csv_files:
        path = os.path.join(script_dir, filename)
        if not os.path.exists(path):
            print(f"Warning: {region} results file not found at {path}")
            continue
        
        try:
            # Read CSV and filter for broken links (Status >= 400) just like report_generator.py
            df = pd.read_csv(path, encoding='utf-8', encoding_errors='ignore')
            df['Status'] = pd.to_numeric(df['Status'], errors='coerce').fillna(0).astype(int)
            
            # Filter for broken links only (Status >= 400)
            broken_df = df[df['Status'] >= 400]
            
            count_before = len(urls)
            for _, row in broken_df.iterrows():
                try:
                    url = str(row.get('URL', '')).strip()
                    # Sanitize URL to ensure valid UTF-8
                    url = url.encode('utf-8', 'ignore').decode('utf-8')
                    if url.startswith('http'):
                        urls.add(url)
                except Exception as e:
                    print(f"Warning: skipping problematic URL in {region}: {e}")
                    continue
            
            count_after = len(urls)
            broken_count = len(broken_df)
            if count_after > count_before:
                print(f"Loaded {count_after - count_before} broken link URLs from {region} ({broken_count} total broken links in file)")
            else:
                print(f"No new broken link URLs from {region} ({broken_count} total broken links in file)")
                
        except Exception as e:
            print(f"Warning: failed to read {region} results from {filename}: {e}")
    
    print(f"Total unique broken link URLs collected: {len(urls)}")
    return list(urls)


def _chunk(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i+size]


def _process_single_url(url, headers, base_url, thread_id):
    """
    Process a single URL to get its view count using New Relic API
    Returns tuple: (url, view_count, success)
    """
    try:
        # Create NRQL query for single URL
        nrql = f"SELECT count(*) FROM PageView WHERE pageUrl LIKE '%{url}%' FACET pageUrl SINCE 30 days ago"
        
        # Make API call
        start_time = time.time()
        response = _fetch_nrql(headers, base_url, nrql)
        api_duration = time.time() - start_time
        
        if response:
            parsed_data = parse_response_data(response)
            # Find matching URL in results
            for item in parsed_data:
                if url in item.get('url', ''):
                    print(f"   🧵 Thread-{thread_id}: {url[:60]}{'...' if len(url) > 60 else ''} = {item['count']} views ({api_duration:.2f}s)")
                    return (url, item['count'], True)
            
            # URL not found in results, means 0 views
            print(f"   🧵 Thread-{thread_id}: {url[:60]}{'...' if len(url) > 60 else ''} = 0 views ({api_duration:.2f}s)")
            return (url, 0, True)
        else:
            print(f"   ❌ Thread-{thread_id}: API failed for {url[:60]}{'...' if len(url) > 60 else ''}")
            return (url, 0, False)
            
    except Exception as e:
        print(f"   ❌ Thread-{thread_id}: Error processing {url[:60]}{'...' if len(url) > 60 else ''}: {e}")
        return (url, 0, False)


def _parse_broken_links_json(script_dir):
    """Parse the brokenlinksview.json file to extract view counts for URLs"""
    json_file = os.path.join(script_dir, 'brokenlinksview.json')
    views_map = {}
    
    if not os.path.exists(json_file):
        print(f"Warning: {json_file} not found")
        return views_map
    
    try:
        with open(json_file, 'r', encoding='utf-8', errors='replace') as f:
            data = json.load(f)
        
        # Navigate through the JSON structure to extract URL view counts
        if data and len(data) > 0 and 'series' in data[0]:
            for series_group in data[0]['series']:
                if 'series' in series_group:
                    for url_data in series_group['series']:
                        url = url_data.get('name', '')
                        if url and 'data' in url_data and len(url_data['data']) > 0:
                            # Extract count from data array [timestamp, count, timestamp]
                            count = url_data['data'][0][1] if len(url_data['data'][0]) > 1 else 0
                            views_map[url] = int(count)
                            print(f"Extracted view count for {url}: {count}")
        
        print(f"Successfully parsed {len(views_map)} URLs from JSON file")
        return views_map
        
    except Exception as e:
        print(f"Error parsing {json_file}: {e}")
        return views_map

def make_api_request(headers, payload, base_url):
    """
    Make the actual API request to New Relic (optional - for live data)
    Note: This requires valid authentication tokens
    """
    url = base_url
    
    print(f"\n🔗 Making API request to: {url}")
    print(f"📋 Request payload: {payload}")
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        print(f"📊 Response status: {response.status_code}")
        print(f"📏 Response size: {len(response.content)} bytes")
        
        if response.status_code == 200:
            json_data = response.json()
            
            # Log response structure
            if isinstance(json_data, dict):
                if 'data' in json_data:
                    print(f"✅ Response contains 'data' field")
                    if isinstance(json_data['data'], dict) and 'actor' in json_data['data']:
                        print(f"✅ Response contains 'actor' field")
                        if 'nrql' in json_data['data']['actor']:
                            nrql_data = json_data['data']['actor']['nrql']
                            if 'results' in nrql_data:
                                results_count = len(nrql_data['results'])
                                print(f"📈 Found {results_count} results in NRQL response")
                            else:
                                print("⚠️ No 'results' field in NRQL response")
                        else:
                            print("⚠️ No 'nrql' field in actor response")
                    else:
                        print("⚠️ No 'actor' field in data response")
                else:
                    print("⚠️ No 'data' field in response")
            else:
                print(f"⚠️ Response is not a dict: {type(json_data)}")
                
            return json_data
        else:
            print(f"❌ API request failed with status {response.status_code}: {response.text}")
            return None
            
    except requests.exceptions.SSLError as e:
        print(f"❌ SSL Error: {e}")
        print("💡 This indicates an SSL/TLS configuration issue with your Python environment")
        return None
    except requests.exceptions.ConnectionError as e:
        print(f"❌ Connection Error: {e}")
        return None
    except requests.exceptions.Timeout as e:
        print(f"❌ Timeout Error: {e}")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Error: {e}")
        if hasattr(e.response, 'text'):
            print(f"📄 Response body: {e.response.text[:500]}...")
        return None
    except requests.exceptions.RequestException as e:
        print(f"❌ Request Error: {e}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return None

def main():
    """
    Main function to process New Relic data and generate HTML
    """
    import os
    
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Get headers and payload dynamically
    headers, payload, base_url = get_dynamic_headers_and_payload()
    
    # Check if environment variables are configured
    if headers is None:
        fallback_html = '''
        <div class="card">
            <h3>📊 Page Views Data</h3>
            <div class="info-message">
                <p><strong>New Relic Configuration Required</strong></p>
                <p>To display page views data, please configure the following environment variables:</p>
                <ul>
                    <li><code>NEWRELIC_BASE_URL</code></li>
                    <li><code>NEWRELIC_ACCOUNT_ID</code></li>
                    <li><code>NEWRELIC_COOKIE</code></li>
                </ul>
                <p>Once configured, regenerate the report to see page views analytics.</p>
            </div>
        </div>
        '''
        
        # Write fallback content to file
        output_file = os.path.join(script_dir, 'page_views_content.html')
        with open(output_file, 'w', encoding='utf-8', errors='ignore') as f:
            f.write(fallback_html)
        
        print("Generated fallback page views content due to missing New Relic configuration.")
        return fallback_html
    
    print(f"Configured request with {len(headers)} headers")
    print(f"Current date/time: {datetime.now()}")

    # 1) Top Products (today) — preserve existing behavior/query
    products_nrql = "SELECT count(*) FROM PageView WHERE pageUrl RLIKE '.*[0-9]+.*' FACET pageUrl ORDER BY count(*) SINCE today"
    print(f"NRQL (Top Products): {products_nrql}")
    resp_products = _fetch_nrql(headers, base_url, products_nrql)
    top_products = parse_response_data(resp_products) if resp_products else []
    print(f"Found {len(top_products)} top products")

    # 2) Top Pages (last 1 day)
    pages_nrql = "SELECT count(*) FROM PageView FACET pageUrl ORDER BY count(*) SINCE 1 day ago"
    print(f"NRQL (Top Pages): {pages_nrql}")
    resp_pages = _fetch_nrql(headers, base_url, pages_nrql)
    top_pages = parse_response_data(resp_pages) if resp_pages else []
    print(f"Found {len(top_pages)} top pages")

    # Store daily data in DB
    today = datetime.utcnow().date().isoformat()
    store_daily_data(today, resp_products, resp_pages)

    # 3) Broken Links Views (30 days) - Process URLs individually with parallel threading
    all_urls = _read_broken_links_urls(script_dir)
    print(f"Collected {len(all_urls)} broken link URLs from CSVs")
    
    # Process broken links using parallel threading
    start_time = time.time()
    views_map = {}
    max_workers = 10  # Number of parallel threads
    
    print(f"\n🔍 PARALLEL BROKEN LINKS PROCESSING STARTED")
    print(f"📊 Total URLs to process: {len(all_urls)}")
    print(f"🧵 Max parallel threads: {max_workers}")
    print(f"⏰ Start time: {time.strftime('%H:%M:%S', time.localtime(start_time))}")
    print(f"{'='*60}")
    
    # Use ThreadPoolExecutor for parallel processing
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all URL processing tasks
        future_to_url = {
            executor.submit(_process_single_url, url, headers, base_url, i % max_workers + 1): url 
            for i, url in enumerate(all_urls)
        }
        
        completed_count = 0
        urls_with_views = 0
        failed_count = 0
        
        # Process completed tasks as they finish
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                result_url, view_count, success = future.result()
                views_map[result_url] = view_count
                
                completed_count += 1
                if view_count > 0:
                    urls_with_views += 1
                if not success:
                    failed_count += 1
                
                # Progress update every 50 URLs
                if completed_count % 50 == 0 or completed_count == len(all_urls):
                    elapsed = time.time() - start_time
                    progress = completed_count / len(all_urls)
                    estimated_total = elapsed / progress if progress > 0 else 0
                    remaining = estimated_total - elapsed
                    
                    print(f"\n📊 Progress Update: {completed_count}/{len(all_urls)} ({progress*100:.1f}%)")
                    print(f"   ✅ URLs with views: {urls_with_views}")
                    print(f"   ❌ Failed requests: {failed_count}")
                    print(f"   ⏳ Elapsed: {elapsed:.1f}s, Estimated remaining: {remaining:.1f}s")
                    print(f"   ⚡ Average per URL: {elapsed/completed_count:.3f}s")
                    
            except Exception as e:
                print(f"   ❌ Exception processing {url}: {e}")
                views_map[url] = 0
                failed_count += 1
    
    # Ensure all URLs are included in the final map
    for url in all_urls:
        if url not in views_map:
            views_map[url] = 0
    
    # Final processing summary
    total_duration = time.time() - start_time
    final_urls_with_views = sum(1 for count in views_map.values() if count > 0)
    total_views = sum(views_map.values())
    
    print(f"\n{'='*60}")
    print(f"🎯 PARALLEL BROKEN LINKS PROCESSING COMPLETED")
    print(f"⏰ Total processing time: {total_duration:.2f} seconds")
    print(f"📊 Final Statistics:")
    print(f"   - Total URLs processed: {len(all_urls)}")
    print(f"   - URLs with view data: {final_urls_with_views}")
    print(f"   - URLs with zero views (broken links): {len(all_urls) - final_urls_with_views}")
    print(f"   - Total page views: {total_views:,}")
    if len(all_urls) > 0:
        print(f"   - Average processing time per URL: {total_duration/len(all_urls):.3f} seconds")
    else:
        print(f"   - Average processing time per URL: N/A (no URLs processed)")
    print(f"   - Parallel efficiency: {max_workers} threads used")
    
    if final_urls_with_views > 0:
        print(f"\n🔥 TOP URLs WITH VIEWS:")
        sorted_views = sorted(views_map.items(), key=lambda x: x[1], reverse=True)
        for i, (url, count) in enumerate(sorted_views[:5]):
            if count > 0:
                print(f"   {i+1}. {url[:70]}{'...' if len(url) > 70 else ''} = {count:,} views")
    
    # Show broken links count clearly
    broken_links_count = len(all_urls) - final_urls_with_views
    print(f"\n🔗 BROKEN LINKS DETECTED: {broken_links_count} URLs with 0 views")
    if broken_links_count > 0:
        print(f"   These URLs are not receiving any traffic and may need attention.")
    
    broken_links_views = [{ 'url': url, 'count': cnt } for url, cnt in views_map.items()]
    print(f"\n✅ Aggregated view counts for {len(broken_links_views)} broken link URLs (using live API data)")
    print(f"{'='*60}\n")

    # Limit sizes for rendering - removed for infinite scroll
    # top_products = top_products[:50]
    # top_pages = top_pages[:50]

    # Generate combined Page Views HTML
    page_views_html = build_page_views_container_html(top_products, top_pages, broken_links_views)

    # Save HTML content to file with proper encoding handling
    output_file = os.path.join(script_dir, 'page_views_content.html')
    # Sanitize HTML content to ensure valid UTF-8
    page_views_html = page_views_html.encode('utf-8', 'ignore').decode('utf-8')
    
    with open(output_file, 'w', encoding='utf-8', errors='ignore') as f:
        f.write(page_views_html)
    print(f"HTML content generated and saved to {output_file}")

    # Also keep legacy file name for backward compatibility
    legacy_output = os.path.join(script_dir, 'top_products_content.html')
    try:
        with open(legacy_output, 'w', encoding='utf-8', errors='ignore') as f:
            f.write(page_views_html)
        print(f"(Compatibility) Also wrote content to {legacy_output}")
    except Exception as e:
        print(f"Warning: could not write legacy file {legacy_output}: {e}")
    
    # Summary of API call results
    print("\n📊 API Call Summary:")
    print(f"   🛍️ Top Products: {len(top_products)} found")
    print(f"   📄 Top Pages: {len(top_pages)} found")
    print(f"   🔗 Broken Links Checked: {len(all_urls)} URLs")
    
    if len(top_products) == 0 and len(top_pages) == 0:
        print("\n⚠️ No data retrieved from New Relic API")
        print("   This is likely due to the SSL module issue preventing HTTPS requests")
        print("   See TROUBLESHOOTING_PAGE_VIEWS.md for solutions")
    else:
        print("\n✅ Successfully retrieved data from New Relic API")

    # Print preview of top 5 products
    for i, product in enumerate(top_products[:5], 1):
        print(f"{i}. {product['url']} - {product['count']:,} views")
    
    return page_views_html

if __name__ == "__main__":
    main()