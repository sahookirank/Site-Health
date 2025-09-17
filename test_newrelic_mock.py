#!/usr/bin/env python3
"""
Mock version of newrelic_top_products.py for testing HTML generation
without requiring API calls
"""

import os
import sys
from datetime import datetime

# Add the current directory to Python path to import from newrelic_top_products
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import functions from the main script
from newrelic_top_products import (
    generate_html_content,
    generate_top_pages_html,
    generate_broken_links_views_html,
    build_page_views_container_html
)

def create_mock_data():
    """Create mock data for testing"""
    
    # Mock top products data
    top_products = [
        {'url': 'https://www.kmart.com.au/product/wireless-bluetooth-headphones-12345', 'count': 1250, 'timestamp': '2025-01-18 10:30:00'},
        {'url': 'https://www.kmart.com.au/product/smart-watch-fitness-tracker-67890', 'count': 980, 'timestamp': '2025-01-18 11:15:00'},
        {'url': 'https://www.kmart.co.nz/product/kitchen-appliance-set-54321', 'count': 750, 'timestamp': '2025-01-18 09:45:00'},
        {'url': 'https://www.kmart.com.au/product/home-decor-lamp-98765', 'count': 620, 'timestamp': '2025-01-18 14:20:00'},
        {'url': 'https://www.kmart.co.nz/product/outdoor-furniture-13579', 'count': 450, 'timestamp': '2025-01-18 16:10:00'}
    ]
    
    # Mock top pages data
    top_pages = [
        {'url': 'https://www.kmart.com.au/', 'count': 5420, 'timestamp': '2025-01-18 12:00:00'},
        {'url': 'https://www.kmart.com.au/category/electronics', 'count': 3210, 'timestamp': '2025-01-18 13:30:00'},
        {'url': 'https://www.kmart.co.nz/category/home-garden', 'count': 2890, 'timestamp': '2025-01-18 15:45:00'},
        {'url': 'https://www.kmart.com.au/category/clothing', 'count': 2150, 'timestamp': '2025-01-18 11:20:00'},
        {'url': 'https://www.kmart.co.nz/category/toys-games', 'count': 1780, 'timestamp': '2025-01-18 14:15:00'}
    ]
    
    # Mock broken links views data
    broken_links_views = [
        {'url': 'https://www.kmart.com.au/broken-link-1', 'count': 25},
        {'url': 'https://www.kmart.co.nz/broken-link-2', 'count': 18},
        {'url': 'https://www.kmart.com.au/broken-link-3', 'count': 12},
        {'url': 'https://www.kmart.co.nz/broken-link-4', 'count': 8},
        {'url': 'https://www.kmart.com.au/broken-link-5', 'count': 3}
    ]
    
    return top_products, top_pages, broken_links_views

def main():
    """Generate HTML with mock data for testing"""
    print("🧪 Testing Page Views HTML generation with mock data...")
    print(f"Current date/time: {datetime.now()}")
    
    # Create mock data
    top_products, top_pages, broken_links_views = create_mock_data()
    
    print(f"Mock data created:")
    print(f"  - Top Products: {len(top_products)} items")
    print(f"  - Top Pages: {len(top_pages)} items")
    print(f"  - Broken Links Views: {len(broken_links_views)} items")
    
    # Generate HTML content
    page_views_html = build_page_views_container_html(top_products, top_pages, broken_links_views)
    
    # Save to test file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_file = os.path.join(script_dir, 'test_page_views_mock.html')
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(page_views_html)
    
    print(f"✅ Mock HTML content generated and saved to {output_file}")
    
    # Print preview of data
    print("\n📊 Mock Data Preview:")
    print("Top Products:")
    for i, product in enumerate(top_products[:3], 1):
        print(f"  {i}. {product['url']} - {product['count']:,} views")
    
    print("\nTop Pages:")
    for i, page in enumerate(top_pages[:3], 1):
        print(f"  {i}. {page['url']} - {page['count']:,} views")
    
    print("\nBroken Links Views:")
    for i, link in enumerate(broken_links_views[:3], 1):
        print(f"  {i}. {link['url']} - {link['count']} views")
    
    return page_views_html

if __name__ == "__main__":
    main()