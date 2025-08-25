#!/usr/bin/env python3
"""
Web Data Collector Script

Automated script for:
1. Navigating to specified websites to collect accurate data
2. Scraping and validating collected data
3. Processing and structuring data into proper JSON format
4. Integrating validated data into existing visualization

Author: AI Assistant
Date: 2024
"""

import requests
import json
import time
import os
import logging
from urllib.parse import urljoin, urlparse, parse_qs
from bs4 import BeautifulSoup
from typing import Dict, List, Optional, Tuple
import pandas as pd
from datetime import datetime
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('web_data_collector.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class WebDataCollector:
    """Main class for web data collection and processing"""
    
    def __init__(self, config_file: str = 'scraper_config.json'):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.config = self.load_config(config_file)
        self.collected_data = []
        self.validation_errors = []
        
    def load_config(self, config_file: str) -> Dict:
        """Load configuration from JSON file"""
        default_config = {
            'target_websites': [
                'https://www.kmart.com.au',
                'https://www.kmart.co.nz'
            ],
            'max_retries': 3,
            'delay_between_requests': 1,
            'timeout': 30,
            'categories_to_extract': ['home', 'clothing', 'toys', 'electronics', 'beauty', 'sports'],
            'output_directory': 'temp',
            'validate_links': True
        }
        
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    # Merge with defaults
                    default_config.update(config)
            return default_config
        except Exception as e:
            logger.warning(f"Could not load config file {config_file}: {e}. Using defaults.")
            return default_config
    
    def navigate_to_website(self, url: str) -> Optional[BeautifulSoup]:
        """Navigate to a website and return parsed HTML"""
        retries = 0
        while retries < self.config['max_retries']:
            try:
                logger.info(f"Navigating to {url} (attempt {retries + 1})")
                response = self.session.get(
                    url, 
                    timeout=self.config['timeout'],
                    allow_redirects=True
                )
                response.raise_for_status()
                
                # Parse HTML
                soup = BeautifulSoup(response.content, 'html.parser')
                logger.info(f"Successfully navigated to {url}")
                return soup
                
            except requests.exceptions.RequestException as e:
                retries += 1
                logger.error(f"Navigation failed for {url}: {e}")
                if retries < self.config['max_retries']:
                    time.sleep(self.config['delay_between_requests'] * retries)
                else:
                    logger.error(f"Max retries exceeded for {url}")
                    return None
        
        return None
    
    def extract_top_level_categories(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """Extract only top-level category names from main navigation"""
        top_categories = []
        
        try:
            # Debug: Print page structure to understand navigation
            logger.info(f"Analyzing page structure for {base_url}")
            
            # Look for various navigation patterns
            nav_patterns = [
                'nav a',
                '.navigation a',
                '.nav a',
                '.menu a',
                '.header a',
                '.main-nav a',
                '.primary-nav a',
                '.top-nav a',
                'header nav a',
                '[role="navigation"] a',
                '.navbar a',
                '.menu-item a',
                '.nav-item a'
            ]
            
            found_categories = set()
            all_links_found = 0
            
            for selector in nav_patterns:
                links = soup.select(selector)
                all_links_found += len(links)
                logger.info(f"Selector '{selector}' found {len(links)} links")
                
                for link in links:
                    href = link.get('href')
                    text = link.get_text(strip=True)
                    
                    if href and text:
                        logger.debug(f"Checking link: '{text}' -> '{href}'")
                        
                        if self.is_top_level_category(href, text):
                            full_url = urljoin(base_url, href)
                            category_name = text.strip()
                            
                            if category_name not in found_categories and len(category_name) > 0:
                                found_categories.add(category_name)
                                top_categories.append({
                                    'name': category_name,
                                    'url': full_url,
                                    'level': 0,
                                    'parent': None
                                })
                                logger.info(f"Added top-level category: '{category_name}' -> '{full_url}'")
            
            logger.info(f"Total links analyzed: {all_links_found}")
            logger.info(f"Found {len(top_categories)} top-level categories: {[cat['name'] for cat in top_categories]}")
            
            # If no categories found, try a more generic approach
            if not top_categories:
                logger.info("No categories found with strict patterns, trying broader search...")
                all_links = soup.find_all('a', href=True)
                logger.info(f"Found {len(all_links)} total links on page")
                
                for link in all_links[:50]:  # Limit to first 50 links to avoid spam
                    href = link.get('href')
                    text = link.get_text(strip=True)
                    
                    if href and text and len(text) < 50:  # Reasonable category name length
                        if self.is_top_level_category(href, text):
                            full_url = urljoin(base_url, href)
                            category_name = text.strip()
                            
                            if category_name not in found_categories and len(category_name) > 0:
                                found_categories.add(category_name)
                                top_categories.append({
                                    'name': category_name,
                                    'url': full_url,
                                    'level': 0,
                                    'parent': None
                                })
                                logger.info(f"Added category from broad search: '{category_name}' -> '{full_url}'")
            
            return top_categories
            
        except Exception as e:
            logger.error(f"Error extracting top-level categories from {base_url}: {e}")
            return []
    
    def is_top_level_category(self, href: str, text: str) -> bool:
        """Determine if a link represents a top-level category"""
        href_lower = href.lower()
        text_lower = text.lower()
        
        # Exclude non-category links
        exclude_patterns = [
            'login', 'register', 'account', 'cart', 'checkout', 'search',
            'contact', 'about', 'help', 'support', 'store-locator',
            'gift-card', 'javascript:', 'mailto:', 'tel:', '#', 'void(0)',
            'privacy', 'terms', 'shipping', 'returns', 'faq', 'blog',
            'careers', 'investor', 'press', 'affiliate'
        ]
        
        for pattern in exclude_patterns:
            if pattern in href_lower or pattern in text_lower:
                return False
        
        # Include main category indicators - both in URL and text
        category_url_patterns = [
            '/category/', '/c/', '/dept/', '/department/', '/shop/',
            '/products/', '/browse/', '/collections/'
        ]
        
        category_text_patterns = [
            'home', 'clothing', 'toys', 'electronics', 'beauty',
            'sports', 'garden', 'automotive', 'baby', 'outdoor',
            'furniture', 'kitchen', 'bedroom', 'bathroom', 'men',
            'women', 'kids', 'fathers-day', 'mothers-day', 'living',
            'tech', 'fashion', 'health', 'fitness', 'books',
            'games', 'music', 'movies', 'appliances', 'tools',
            'office', 'school', 'party', 'seasonal', 'clearance',
            'sale', 'new arrivals', 'trending', 'featured'
        ]
        
        # Check URL patterns
        for pattern in category_url_patterns:
            if pattern in href_lower:
                return True
        
        # Check text patterns
        for pattern in category_text_patterns:
            if pattern in text_lower:
                return True
        
        # Additional heuristics for category detection
        # Short, descriptive text that could be a category
        if len(text.strip()) > 2 and len(text.strip()) < 30:
            # Check if it looks like a category name (no special chars, reasonable length)
            if text.replace(' ', '').replace('&', '').replace('-', '').isalnum():
                # If the href contains common category indicators
                if any(indicator in href_lower for indicator in ['/', 'category', 'shop', 'browse', 'dept']):
                    return True
        
        return False
    
    def extract_category_hierarchy_from_page(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """Extract all category hierarchy from a single page without navigation"""
        all_categories = []
        
        try:
            # First try to extract from specific list items with data-testid attributes
            testid_categories = self.extract_from_testid_elements(soup, base_url)
            if testid_categories:
                logger.info(f"Extracted {len(testid_categories)} categories from data-testid elements")
                all_categories.extend(testid_categories)
            
            # Look for various category structures on the page
            category_selectors = [
                # Navigation menus
                'nav a', '.navigation a', '.nav a', '.menu a',
                # Category sections
                '.category a', '.categories a', '.category-list a',
                '.category-grid a', '.category-nav a', '.sub-nav a',
                # Dropdown menus and mega menus
                '.dropdown a', '.mega-menu a', '.submenu a',
                # Sidebar categories
                '.sidebar a', '.filter a', '.facet a',
                # Footer categories
                'footer a',
                # Generic category links
                'a[href*="/category/"]', 'a[href*="/c/"]', 'a[href*="/dept/"]',
                'a[href*="/shop/"]', 'a[href*="/browse/"]'
            ]
            
            found_categories = set()
            category_hierarchy = {}
            
            for selector in category_selectors:
                links = soup.select(selector)
                logger.info(f"Selector '{selector}' found {len(links)} potential category links")
                
                for link in links:
                    href = link.get('href')
                    text = link.get_text(strip=True)
                    
                    if href and text and len(text) < 100:  # Reasonable category name length
                        full_url = urljoin(base_url, href)
                        
                        # Determine category level from URL structure
                        level = self.determine_category_level(full_url)
                        parent = self.extract_parent_category(full_url)
                        
                        if self.is_category_text(text) and text not in found_categories:
                            found_categories.add(text)
                            
                            category_data = {
                                'name': text.strip(),
                                'url': full_url,
                                'level': level,
                                'parent': parent,
                                'extracted_from': 'page_structure'
                            }
                            
                            all_categories.append(category_data)
                            
                            # Build hierarchy mapping
                            if parent:
                                if parent not in category_hierarchy:
                                    category_hierarchy[parent] = []
                                category_hierarchy[parent].append(text)
            
            # Also extract from structured data (JSON-LD, microdata)
            structured_categories = self.extract_from_structured_data(soup)
            all_categories.extend(structured_categories)
            
            logger.info(f"Extracted {len(all_categories)} categories from page structure")
            return all_categories
            
        except Exception as e:
            logger.error(f"Error extracting category hierarchy from page: {e}")
            return []
    
    def determine_category_level(self, url: str) -> int:
        """Determine category level from URL structure"""
        parsed_url = urlparse(url)
        path_parts = [part for part in parsed_url.path.split('/') if part]
        
        # Count depth after category indicators
        category_indicators = ['category', 'categories', 'c', 'dept', 'department', 'shop', 'browse']
        
        for i, part in enumerate(path_parts):
            if part.lower() in category_indicators:
                # Return the depth after the category indicator
                return len(path_parts) - i - 1
        
        # Default level based on path depth
        return min(len(path_parts) - 1, 3)
    
    def extract_parent_category(self, url: str) -> Optional[str]:
        """Extract parent category name from URL structure"""
        parsed_url = urlparse(url)
        path_parts = [part for part in parsed_url.path.split('/') if part]
        
        category_indicators = ['category', 'categories', 'c', 'dept', 'department', 'shop', 'browse']
        
        for i, part in enumerate(path_parts):
            if part.lower() in category_indicators and i + 1 < len(path_parts):
                if i + 2 < len(path_parts):  # Has parent
                    return path_parts[i + 1].replace('-', ' ').replace('_', ' ').title()
        
        return None
    
    def is_category_text(self, text: str) -> bool:
        """Determine if text represents a category name"""
        text_lower = text.lower().strip()
        
        # Exclude non-category text
        exclude_patterns = [
            'login', 'register', 'account', 'cart', 'checkout', 'search',
            'contact', 'about', 'help', 'support', 'privacy', 'terms',
            'shipping', 'returns', 'faq', 'blog', 'careers', 'view all',
            'see more', 'load more', 'next', 'previous', 'page', 'sort by'
        ]
        
        for pattern in exclude_patterns:
            if pattern in text_lower:
                return False
        
        # Include category-like text
        if len(text_lower) > 1 and len(text_lower) < 50:
            # Check for category keywords
            category_keywords = [
                'home', 'clothing', 'toys', 'electronics', 'beauty', 'sports',
                'garden', 'automotive', 'baby', 'outdoor', 'furniture', 'kitchen',
                'bedroom', 'bathroom', 'men', 'women', 'kids', 'tech', 'fashion',
                'health', 'fitness', 'books', 'games', 'music', 'movies',
                'appliances', 'tools', 'office', 'school', 'party', 'seasonal'
            ]
            
            for keyword in category_keywords:
                if keyword in text_lower:
                    return True
            
            # General heuristic: short, alphanumeric text
            if text.replace(' ', '').replace('&', '').replace('-', '').replace("'", '').isalnum():
                return True
        
        return False
    
    def extract_from_testid_elements(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """Extract categories from list items with specific data-testid attributes"""
        categories = []
        
        try:
            # Target specific data-testid values: levelzero, leveltwo, levelthree, levelfour
            target_testids = ['levelzero', 'leveltwo', 'levelthree', 'levelfour']
            
            for testid in target_testids:
                elements = soup.find_all('li', {'data-testid': testid})
                logger.info(f"Found {len(elements)} <li> elements with data-testid='{testid}'")
                
                for element in elements:
                    # Extract text content without markup
                    text_content = element.get_text(strip=True)
                    
                    if text_content:
                        # Try to find links within the element
                        links = element.find_all('a', href=True)
                        
                        if links:
                            # Use the first link found
                            link = links[0]
                            href = link.get('href')
                            full_url = urljoin(base_url, href)
                        else:
                            # No link found, create a placeholder URL
                            full_url = f"{base_url}#{testid}-{len(categories)}"
                        
                        # Determine level based on testid
                        level_map = {
                            'levelzero': 0,
                            'leveltwo': 2, 
                            'levelthree': 3,
                            'levelfour': 4
                        }
                        
                        level = level_map.get(testid, 0)
                        parent = self.extract_parent_category(full_url) if level > 0 else None
                        
                        categories.append({
                            'name': text_content,
                            'url': full_url,
                            'level': level,
                            'parent': parent,
                            'extracted_from': f'testid_{testid}'
                        })
            
            logger.info(f"Extracted {len(categories)} categories from specific data-testid elements")
            return categories
            
        except Exception as e:
            logger.error(f"Error extracting from data-testid elements: {e}")
            return []
    
    def extract_from_structured_data(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract categories from structured data (JSON-LD, microdata)"""
        categories = []
        
        try:
            # Look for JSON-LD structured data
            json_scripts = soup.find_all('script', type='application/ld+json')
            for script in json_scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict) and 'itemListElement' in data:
                        for item in data['itemListElement']:
                            if 'name' in item:
                                categories.append({
                                    'name': item['name'],
                                    'url': item.get('url', ''),
                                    'level': 0,
                                    'parent': None,
                                    'extracted_from': 'structured_data'
                                })
                except json.JSONDecodeError:
                    continue
            
            logger.info(f"Extracted {len(categories)} categories from structured data")
            return categories
            
        except Exception as e:
            logger.error(f"Error extracting structured data: {e}")
            return []
    
    def is_valid_subcategory(self, url: str, text: str, parent_url: str) -> bool:
        """Determine if a link represents a valid subcategory"""
        url_lower = url.lower()
        text_lower = text.lower()
        parent_lower = parent_url.lower()
        
        # Must contain category indicators
        if not any(indicator in url_lower for indicator in ['/category/', '/c/', '/dept/']):
            return False
        
        # Should be a deeper path than parent
        if not url_lower.startswith(parent_lower.rstrip('/')):
            return False
        
        # Exclude non-category links
        exclude_patterns = [
            'login', 'register', 'account', 'cart', 'checkout', 'search',
            'javascript:', 'mailto:', 'tel:', '#', 'void(0)',
            'clearance', 'sale', 'new-arrivals', 'trending'
        ]
        
        for pattern in exclude_patterns:
            if pattern in url_lower or pattern in text_lower:
                return False
        
        return True
    
    def is_category_link(self, url: str, text: str) -> bool:
        """Determine if a link is category-related"""
        url_lower = url.lower()
        text_lower = text.lower()
        
        # URL patterns that indicate categories
        category_patterns = [
            '/category/',
            '/categories/',
            '/c/',
            '/dept/',
            '/department/'
        ]
        
        # Text patterns that indicate categories
        category_keywords = self.config['categories_to_extract'] + [
            'shop', 'browse', 'department', 'section'
        ]
        
        # Check URL patterns
        for pattern in category_patterns:
            if pattern in url_lower:
                return True
        
        # Check text keywords
        for keyword in category_keywords:
            if keyword in text_lower:
                return True
        
        return False
    
    def extract_category_name(self, url: str, text: str) -> str:
        """Extract category name from URL or link text"""
        # Try to extract from URL first
        parsed_url = urlparse(url)
        path_parts = [part for part in parsed_url.path.split('/') if part]
        
        # Look for category in URL path
        for i, part in enumerate(path_parts):
            if part.lower() in ['category', 'categories', 'c', 'dept', 'department']:
                if i + 1 < len(path_parts):
                    return path_parts[i + 1].replace('-', ' ').replace('_', ' ').title()
        
        # Fallback to link text
        return text.strip().title()
    
    def validate_data(self, data: List[Dict]) -> Tuple[List[Dict], List[str]]:
        """Validate collected data and return valid data and errors"""
        valid_data = []
        errors = []
        
        for item in data:
            try:
                # Required fields validation
                required_fields = ['url', 'text', 'category']
                for field in required_fields:
                    if field not in item or not item[field]:
                        raise ValueError(f"Missing or empty required field: {field}")
                
                # URL validation
                parsed_url = urlparse(item['url'])
                if not parsed_url.scheme or not parsed_url.netloc:
                    raise ValueError(f"Invalid URL format: {item['url']}")
                
                # Text validation
                if len(item['text']) > 200:
                    item['text'] = item['text'][:200] + '...'
                
                # Category name validation
                item['category'] = re.sub(r'[^a-zA-Z0-9\s\-_]', '', item['category'])
                
                # Link validation (if enabled)
                if self.config['validate_links']:
                    if not self.validate_link(item['url']):
                        item['status'] = 'invalid'
                        errors.append(f"Link validation failed for: {item['url']}")
                    else:
                        item['status'] = 'valid'
                
                valid_data.append(item)
                
            except Exception as e:
                error_msg = f"Validation error for item {item}: {e}"
                errors.append(error_msg)
                logger.warning(error_msg)
        
        logger.info(f"Validated {len(valid_data)} items, {len(errors)} errors")
        return valid_data, errors
    
    def validate_link(self, url: str) -> bool:
        """Validate if a link is accessible"""
        try:
            response = self.session.head(url, timeout=10, allow_redirects=True)
            return response.status_code < 400
        except:
            return False
    
    def process_to_json(self, data: List[Dict], region: str) -> Dict:
        """Process data into structured JSON format"""
        processed_data = {
            'region': region,
            'collection_timestamp': datetime.now().isoformat(),
            'total_categories': 0,
            'categories': {},
            'metadata': {
                'total_links': len(data),
                'valid_links': len([item for item in data if item.get('status') == 'valid']),
                'invalid_links': len([item for item in data if item.get('status') == 'invalid']),
                'collection_method': 'automated_scraping'
            }
        }
        
        # Group by category
        category_groups = {}
        for item in data:
            category = item['category']
            if category not in category_groups:
                category_groups[category] = {
                    'count': 0,
                    'subcategories': [],
                    'urls': []
                }
            
            category_groups[category]['count'] += 1
            category_groups[category]['urls'].append(item['url'])
            
            # Extract subcategories from URL path
            parsed_url = urlparse(item['url'])
            path_parts = [part for part in parsed_url.path.split('/') if part]
            
            # Look for subcategories after main category
            for i, part in enumerate(path_parts):
                if part.lower() == category.lower().replace(' ', '-'):
                    if i + 1 < len(path_parts):
                        subcategory = path_parts[i + 1].replace('-', ' ').replace('_', ' ').title()
                        if subcategory not in category_groups[category]['subcategories']:
                            category_groups[category]['subcategories'].append(subcategory)
        
        processed_data['categories'] = category_groups
        processed_data['total_categories'] = len(category_groups)
        
        logger.info(f"Processed {len(data)} items into {len(category_groups)} categories for {region}")
        return processed_data
    
    def save_json_data(self, data: Dict, filename: str) -> bool:
        """Save processed data to JSON file"""
        try:
            output_dir = self.config['output_directory']
            os.makedirs(output_dir, exist_ok=True)
            
            filepath = os.path.join(output_dir, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Data saved to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving data to {filename}: {e}")
            return False
    
    def integrate_with_visualization(self, json_data: Dict, region: str) -> bool:
        """Integrate processed data with existing visualization system"""
        try:
            # Convert to format expected by existing visualization
            visualization_data = {
                category: {
                    'count': info['count'],
                    'subcategories': info['subcategories'],
                    'urls': info['urls']
                }
                for category, info in json_data['categories'].items()
            }
            
            # Save in format expected by report generator
            output_filename = f"{region.lower()}_categories.json"
            return self.save_json_data(visualization_data, output_filename)
            
        except Exception as e:
            logger.error(f"Error integrating with visualization for {region}: {e}")
            return False
    
    def collect_website_data(self, url: str) -> List[Dict]:
        """Collect data from a single website using optimized single-page extraction"""
        logger.info(f"Starting optimized data collection for {url}")
        
        soup = self.navigate_to_website(url)
        if not soup:
            logger.error(f"Failed to navigate to {url}")
            return []
        
        # Extract all categories from the main page without navigation
        all_categories = self.extract_category_hierarchy_from_page(soup, url)
        
        if not all_categories:
            logger.warning(f"No categories found on {url}")
            return []
        
        # Convert categories to items format
        all_items = []
        
        for category in all_categories:
            try:
                item = {
                    'url': category['url'],
                    'text': category['name'],
                    'category': category['parent'] if category['parent'] else 'Top Level',
                    'level': category['level'],
                    'parent': category['parent'],
                    'extraction_method': category.get('extracted_from', 'page_structure'),
                    'discovered_at': datetime.now().isoformat()
                }
                all_items.append(item)
                
            except Exception as e:
                error_msg = f"Error processing category '{category.get('name', 'unknown')}': {e}"
                logger.error(error_msg)
        
        logger.info(f"Total items collected: {len(all_items)} (optimized single-page extraction)")
        return all_items
    
    def run_collection(self) -> Dict[str, any]:
        """Run the complete data collection process"""
        logger.info("Starting web data collection process")
        
        results = {
            'success': True,
            'collected_data': {},
            'validation_errors': [],
            'processing_errors': []
        }
        
        try:
            for website_url in self.config['target_websites']:
                try:
                    # Determine region from URL
                    if '.com.au' in website_url:
                        region = 'AU'
                    elif '.co.nz' in website_url:
                        region = 'NZ'
                    else:
                        region = 'UNKNOWN'
                    
                    logger.info(f"Processing {region} website: {website_url}")
                    
                    # Collect data
                    raw_data = self.collect_website_data(website_url)
                    
                    if raw_data:
                        # Validate data
                        valid_data, validation_errors = self.validate_data(raw_data)
                        results['validation_errors'].extend(validation_errors)
                        
                        # Process to JSON
                        processed_data = self.process_to_json(valid_data, region)
                        
                        # Save raw processed data
                        raw_filename = f"{region.lower()}_raw_data.json"
                        self.save_json_data(processed_data, raw_filename)
                        
                        # Integrate with visualization
                        if self.integrate_with_visualization(processed_data, region):
                            logger.info(f"Successfully integrated {region} data with visualization")
                        else:
                            results['processing_errors'].append(f"Failed to integrate {region} data")
                        
                        results['collected_data'][region] = {
                            'total_items': len(raw_data),
                            'valid_items': len(valid_data),
                            'categories': len(processed_data['categories'])
                        }
                    
                    else:
                        logger.warning(f"No data collected from {website_url}")
                        results['processing_errors'].append(f"No data collected from {website_url}")
                
                except Exception as e:
                    error_msg = f"Error processing {website_url}: {e}"
                    logger.error(error_msg)
                    results['processing_errors'].append(error_msg)
                    results['success'] = False
            
            # Generate summary report
            self.generate_summary_report(results)
            
        except Exception as e:
            logger.error(f"Critical error in collection process: {e}")
            results['success'] = False
            results['processing_errors'].append(f"Critical error: {e}")
        
        return results
    
    def generate_summary_report(self, results: Dict) -> None:
        """Generate a summary report of the collection process"""
        summary = {
            'collection_timestamp': datetime.now().isoformat(),
            'overall_success': results['success'],
            'websites_processed': len(self.config['target_websites']),
            'regions_collected': list(results['collected_data'].keys()),
            'total_validation_errors': len(results['validation_errors']),
            'total_processing_errors': len(results['processing_errors']),
            'detailed_results': results['collected_data']
        }
        
        self.save_json_data(summary, 'collection_summary.json')
        logger.info(f"Collection complete. Summary saved to collection_summary.json")

def main():
    """Main function to run the web data collector"""
    collector = WebDataCollector()
    results = collector.run_collection()
    
    if results['success']:
        print("✅ Web data collection completed successfully!")
        print(f"Collected data for {len(results['collected_data'])} regions")
        for region, stats in results['collected_data'].items():
            print(f"  {region}: {stats['valid_items']} valid items, {stats['categories']} categories")
    else:
        print("❌ Web data collection completed with errors")
        print(f"Validation errors: {len(results['validation_errors'])}")
        print(f"Processing errors: {len(results['processing_errors'])}")
    
    return results

if __name__ == "__main__":
    main()