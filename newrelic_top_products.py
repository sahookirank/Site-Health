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

def get_dynamic_headers_and_payload():
    """
    Get headers and payload using cookie from environment variables.
    """
    metadata_url = os.getenv('NEWRELIC_BASE_URL')
    cookie = os.getenv('NEWRELIC_COOKIE')
    account_id = os.getenv('NEWRELIC_ACCOUNT_ID')

    if not metadata_url:
        raise ValueError("NEWRELIC_BASE_URL environment variable not set.")

    if not cookie:
        print("Warning: NEWRELIC_COOKIE environment variable not set. Requests may fail.")

    if not account_id:
        raise ValueError("NEWRELIC_ACCOUNT_ID environment variable not set.")

    base_url = "https://chartdata.service.newrelic.com"  # API host

    # Build headers with all required fields
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (compatible; Link-Checker/1.0)',
        'Accept': 'application/json',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive'
    }
    
    if cookie:
        headers['Cookie'] = cookie
    
    # Build payload
    payload = [
        {
            "account_ids": [int(account_id)],
            "metadata": {
                "artifact_id": "viz.billboard",
                "entity_guid": None,
                "root_artifact_id": "unified-data-exploration.home",
                "url": metadata_url
            },
            "nrql": "SELECT count(*) FROM PageView WHERE pageUrl RLIKE '.*[0-9]+.*' FACET pageUrl ORDER BY count(*) LIMIT 100 SINCE 1 day ago",
            "raw": False,
            "async": False,
            "duration": None,
            "end_time": None,
            "begin_time": None
        }
    ]
    
    return headers, payload, base_url

def parse_response_file(file_path):
    """
    Parse the New Relic API response file to extract product data
    """
    with open(file_path, 'r') as f:
        response_data = json.load(f)
    
    products = []
    
    if response_data and len(response_data) > 0:
        series_data = response_data[0].get('series', [])
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
                        <tr class="filters">
                            <th><input type='text' placeholder='Filter ...' style='width: 90%;' /></th>
                            <th><input type='text' placeholder='Filter ...' style='width: 90%;' /></th>
                            <th><input type='text' placeholder='Filter ...' style='width: 90%;' /></th>
                            <th><input type='text' placeholder='Filter ...' style='width: 90%;' /></th>
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
        
        html_content += f'''
                        <tr>
                            <td>{i}</td>
                            <td>
                                <a href="{product['url']}" target="_blank" title="{product['url']}">
                                    {product_name}
                                </a>
                                <br><small style="color: #666;">{product['url']}</small>
                            </td>
                            <td><strong>{product['count']:,}</strong></td>
                            <td>{product['timestamp']}</td>
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

def make_api_request(headers, payload, base_url):
    """
    Make the actual API request to New Relic (optional - for live data)
    Note: This requires valid authentication tokens
    """
    url = f"{base_url}/v3/nrql" if "chartdata" in base_url else f"{base_url}/graphql"
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"API request failed with status {response.status_code}: {response.text}")
            return None
    except Exception as e:
        print(f"Error making API request: {e}")
        return None

def main():
    """
    Main function to process New Relic data and generate HTML
    """
    import os
    
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Get headers and payload dynamically (environment variables with file fallback)
    headers, payload, base_url = get_dynamic_headers_and_payload()
    print(f"Configured request with {len(headers)} headers")
    
    # File path for response data (still used for static data)
    response_file = os.path.join(script_dir, 'nrql', 'response.json')
    
    # Parse response file
    products = parse_response_file(response_file)
    print(f"Found {len(products)} products")
    
    # Limit to top 50 products (excluding "Other" entries)
    top_products = products[:50]
    print(f"Displaying top {len(top_products)} products (excluding 'Other' entries)")
    
    # Generate HTML content
    html_content = generate_html_content(top_products)
    
    # Save HTML content to file
    output_file = os.path.join(script_dir, 'top_products_content.html')
    with open(output_file, 'w') as f:
        f.write(html_content)
    
    print(f"HTML content generated and saved to {output_file}")
    print(f"Top 5 products (from filtered 50):")
    for i, product in enumerate(top_products[:5], 1):
        print(f"{i}. {product['url']} - {product['count']:,} views")
    
    return html_content

if __name__ == "__main__":
    main()