#!/usr/bin/env python3
"""
New Relic Top Products Data Processor
Generates HTML content for top product URLs and their page visit counts
"""

import json
import requests
from datetime import datetime
from urllib.parse import unquote

def parse_request_file(file_path):
    """
    Parse the New Relic API request file to extract headers and payload
    """
    with open(file_path, 'r') as f:
        content = f.read()
    
    lines = content.strip().split('\n')
    headers = {}
    payload_start = False
    payload_lines = []
    
    for line in lines:
        if line.startswith('POST') or line.startswith('200') or line.startswith('1821 ms'):
            continue
        elif ':' in line and not payload_start:
            if line.strip().startswith('['):
                payload_start = True
                payload_lines.append(line)
            else:
                key, value = line.split(':', 1)
                headers[key.strip()] = value.strip()
        elif payload_start:
            payload_lines.append(line)
    
    payload_str = '\n'.join(payload_lines)
    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError:
        payload = None
    
    return headers, payload

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

def make_api_request(headers, payload):
    """
    Make the actual API request to New Relic (optional - for live data)
    Note: This requires valid authentication tokens
    """
    url = "https://chartdata.service.newrelic.com/v3/nrql"
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"API request failed with status {response.status_code}")
            return None
    except Exception as e:
        print(f"Error making API request: {e}")
        return None

def main():
    """
    Main function to process New Relic data and generate HTML
    """
    # File paths
    request_file = '/Users/ksahoo/Documents/brokenlinkchecker-private/Link-Checker/nrql/request.txt'
    response_file = '/Users/ksahoo/Documents/brokenlinkchecker-private/Link-Checker/nrql/response.json'
    
    # Parse request file
    headers, payload = parse_request_file(request_file)
    print(f"Parsed request with {len(headers)} headers")
    
    # Parse response file
    products = parse_response_file(response_file)
    print(f"Found {len(products)} products")
    
    # Limit to top 50 products (excluding "Other" entries)
    top_products = products[:50]
    print(f"Displaying top {len(top_products)} products (excluding 'Other' entries)")
    
    # Generate HTML content
    html_content = generate_html_content(top_products)
    
    # Save HTML content to file
    output_file = '/Users/ksahoo/Documents/brokenlinkchecker-private/Link-Checker/top_products_content.html'
    with open(output_file, 'w') as f:
        f.write(html_content)
    
    print(f"HTML content generated and saved to {output_file}")
    print(f"Top 5 products (from filtered 50):")
    for i, product in enumerate(top_products[:5], 1):
        print(f"{i}. {product['url']} - {product['count']:,} views")
    
    return html_content

if __name__ == "__main__":
    main()