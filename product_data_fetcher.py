#!/usr/bin/env python3
"""
Standalone Product Data Fetcher for Broken Link Check Workflow

This script fetches product SKUs and generates CSV files for the link checker workflow.
It handles all product data operations including database management and CSV generation.
"""

import os
import sys
import sqlite3
import json
import requests
import pandas as pd
import logging
from datetime import datetime
from typing import List, Dict, Optional
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ProductDataFetcher:
    def __init__(self):
        self.db_path = "product_availability.db"
        self.base_url = "https://mc-api.australia-southeast1.gcp.commercetools.com"
        self.search_endpoint = f"{self.base_url}/proxy/pim-search/kmart-production/search/products"
        self.graphql_endpoint = f"{self.base_url}/graphql"
        
        # Get configuration from environment
        self.auth_token = os.getenv('COMMERCETOOL_AUTH_TOKEN')
        self.project_key = os.getenv('COMMERCETOOL_PROJECT_KEY', 'kmart-production')
        self.max_products = int(os.getenv('MAX_PRODUCTS', '100'))
        
        if not self.auth_token:
            logger.warning("COMMERCETOOL_AUTH_TOKEN not found, will create fallback data")
            self.auth_token = None
        
        # Headers for API requests
        if self.auth_token:
            self.search_headers = {
                "accept": "application/json",
                "content-type": "application/json",
                "authorization": f"Bearer {self.auth_token}",
                "x-project-key": self.project_key,
                "cache-control": "no-cache"
            }
            
            self.graphql_headers = {
                "accept": "application/json",
                "content-type": "application/json",
                "authorization": f"Bearer {self.auth_token}",
                "x-project-key": self.project_key,
                "x-graphql-operation-name": "GeneralInfoTabQuery",
                "x-graphql-target": "ctp",
                "cache-control": "no-cache"
            }

    def initialize_database(self):
        """Initialize the product database if it doesn't exist."""
        try:
            if not os.path.exists(self.db_path):
                logger.info("Creating new product database")
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS "products-in-links" (
                        ID INTEGER PRIMARY KEY AUTOINCREMENT,
                        SKU TEXT UNIQUE NOT NULL,
                        DETAILS TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_sku ON "products-in-links" (SKU)')
                conn.commit()
                conn.close()
                logger.info("Database initialized successfully")
            else:
                logger.info("Using existing product database")
                
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            return False
        return True

    def extract_skus_from_csv_files(self) -> List[str]:
        """Extract SKUs from AU and NZ link check CSV files."""
        skus = set()
        csv_files = ['au_link_check_results.csv', 'nz_link_check_results.csv']

        for csv_file in csv_files:
            if not os.path.exists(csv_file):
                logger.warning(f"CSV file not found: {csv_file}")
                continue

            try:
                import pandas as pd
                df = pd.read_csv(csv_file)

                if 'URL' not in df.columns:
                    logger.warning(f"No URL column found in {csv_file}")
                    continue

                logger.info(f"Processing {len(df)} URLs from {csv_file}")

                # Extract SKUs from URLs using regex patterns
                import re
                for url in df['URL'].dropna():
                    # Pattern for Kmart AU: /product/[SKU]/
                    au_match = re.search(r'/product/([A-Za-z0-9\-_]+)/', str(url))
                    if au_match:
                        skus.add(au_match.group(1))
                        continue

                    # Pattern for Kmart NZ: /p/[SKU]/
                    nz_match = re.search(r'/p/([A-Za-z0-9\-_]+)/', str(url))
                    if nz_match:
                        skus.add(nz_match.group(1))
                        continue

                    # Additional patterns for product URLs
                    # Pattern: /[SKU] at end of URL
                    end_match = re.search(r'/([A-Za-z0-9\-_]+)/?$', str(url))
                    if end_match and len(end_match.group(1)) >= 6:  # Minimum SKU length
                        potential_sku = end_match.group(1)
                        # Filter out common non-SKU endings
                        if not any(word in potential_sku.lower() for word in ['home', 'category', 'search', 'page']):
                            skus.add(potential_sku)

                logger.info(f"Extracted {len(skus)} unique SKUs from {csv_file}")

            except Exception as e:
                logger.error(f"Error processing {csv_file}: {e}")

        sku_list = list(skus)
        logger.info(f"Total unique SKUs extracted: {len(sku_list)}")
        return sku_list[:self.max_products]  # Limit to max_products

    def store_skus_in_database(self, skus: List[str]) -> int:
        """Store SKUs in database with deduplication."""
        if not skus:
            logger.warning("No SKUs to store in database")
            return 0

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            stored_count = 0
            for sku in skus:
                try:
                    # Insert with deduplication (IGNORE duplicate SKUs)
                    cursor.execute(
                        'INSERT OR IGNORE INTO "products-in-links" (SKU, DETAILS) VALUES (?, ?)',
                        (sku, json.dumps({"status": "pending", "extracted_at": datetime.now().isoformat()}))
                    )
                    if cursor.rowcount > 0:
                        stored_count += 1
                except Exception as e:
                    logger.error(f"Error storing SKU {sku}: {e}")

            conn.commit()
            conn.close()

            logger.info(f"Stored {stored_count} new SKUs in database")
            return stored_count

        except Exception as e:
            logger.error(f"Error storing SKUs in database: {e}")
            return 0

    def get_products_from_database(self) -> List[Dict]:
        """Get products from the local database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            query = 'SELECT ID, SKU, DETAILS FROM "products-in-links" LIMIT ?'
            cursor.execute(query, (self.max_products,))

            rows = cursor.fetchall()
            conn.close()

            products = []
            for row in rows:
                try:
                    details = json.loads(row[2]) if row[2] else {}
                except json.JSONDecodeError:
                    details = {"error": "Invalid JSON data"}

                products.append({
                    "id": row[0],
                    "sku": row[1],
                    "details": details
                })

            logger.info(f"Retrieved {len(products)} products from database")
            return products

        except Exception as e:
            logger.error(f"Error retrieving products from database: {e}")
            return []

    def search_product_by_sku(self, sku: str) -> Optional[str]:
        """Search for product ID using SKU via CommerceTools search API."""
        if not self.auth_token:
            return None

        try:
            search_payload = {
                "query": {
                    "term": {
                        "masterVariant.sku": sku
                    }
                },
                "limit": 1
            }

            response = requests.post(
                self.search_endpoint,
                headers=self.search_headers,
                json=search_payload,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('results') and len(data['results']) > 0:
                    product_id = data['results'][0].get('id')
                    logger.debug(f"Found product ID {product_id} for SKU {sku}")
                    return product_id
                else:
                    logger.debug(f"No product found for SKU {sku}")
                    return None
            else:
                logger.warning(f"Search API error for SKU {sku}: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error searching for SKU {sku}: {e}")
            return None

    def fetch_product_details(self, product_id: str) -> Optional[Dict]:
        """Fetch detailed product information via GraphQL API."""
        if not self.auth_token:
            return None

        try:
            graphql_query = {
                "query": """
                query GetProduct($id: String!) {
                    product(id: $id) {
                        id
                        key
                        masterData {
                            current {
                                name(locale: "en-AU")
                                description(locale: "en-AU")
                                masterVariant {
                                    id
                                    sku
                                    attributes {
                                        name
                                        value
                                    }
                                }
                                categories {
                                    id
                                    name(locale: "en-AU")
                                }
                            }
                        }
                    }
                }
                """,
                "variables": {
                    "id": product_id
                }
            }

            response = requests.post(
                self.graphql_endpoint,
                headers=self.graphql_headers,
                json=graphql_query,
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                if 'data' in data and data['data'].get('product'):
                    product_data = data['data']['product']
                    logger.debug(f"Fetched details for product {product_id}")
                    return product_data
                else:
                    logger.warning(f"No product data returned for ID {product_id}")
                    return None
            else:
                logger.warning(f"GraphQL API error for product {product_id}: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error fetching details for product {product_id}: {e}")
            return None

    def fetch_products_from_api(self) -> List[Dict]:
        """Fetch products from the CommerceTools API."""
        if not self.auth_token:
            logger.warning("No auth token available, skipping API fetch")
            return []

        # Get products from database that need API data
        db_products = self.get_products_from_database()
        if not db_products:
            logger.info("No products in database to fetch from API")
            return []

        results = []
        processed_count = 0

        logger.info(f"Starting API fetch for {len(db_products)} products")

        for product in db_products:
            sku = product['sku']
            processed_count += 1

            logger.info(f"Processing SKU {sku} ({processed_count}/{len(db_products)})")

            # Search for product ID
            product_id = self.search_product_by_sku(sku)
            if not product_id:
                # Create fallback entry
                results.append({
                    "SKU": sku,
                    "ID": "not-found",
                    "DETAIL": json.dumps({
                        "status": "not_found",
                        "message": "Product not found in API",
                        "processed_at": datetime.now().isoformat()
                    })
                })
                continue

            # Fetch detailed product information
            product_details = self.fetch_product_details(product_id)
            if product_details:
                # Extract relevant information
                detail_data = {
                    "status": "found",
                    "product_id": product_id,
                    "name": "",
                    "description": "",
                    "attributes": {},
                    "categories": [],
                    "processed_at": datetime.now().isoformat()
                }

                # Extract name and description
                current_data = product_details.get('masterData', {}).get('current', {})
                detail_data["name"] = current_data.get('name', '')
                detail_data["description"] = current_data.get('description', '')

                # Extract attributes
                master_variant = current_data.get('masterVariant', {})
                attributes = master_variant.get('attributes', [])
                for attr in attributes:
                    if attr.get('name') and attr.get('value') is not None:
                        detail_data["attributes"][attr['name']] = attr['value']

                # Extract categories
                categories = current_data.get('categories', [])
                detail_data["categories"] = [cat.get('name', '') for cat in categories]

                results.append({
                    "SKU": sku,
                    "ID": product_id,
                    "DETAIL": json.dumps(detail_data)
                })
            else:
                # Create fallback entry for API error
                results.append({
                    "SKU": sku,
                    "ID": product_id,
                    "DETAIL": json.dumps({
                        "status": "api_error",
                        "message": "Failed to fetch product details",
                        "processed_at": datetime.now().isoformat()
                    })
                })

            # Rate limiting - small delay between API calls
            time.sleep(0.1)

        logger.info(f"API fetch completed. Processed {len(results)} products")
        return results

    def create_fallback_data(self) -> List[Dict]:
        """Create fallback data when API is not available."""
        logger.info("Creating fallback product data")
        return [
            {
                "SKU": "FALLBACK001",
                "ID": "fallback-id-1",
                "DETAIL": json.dumps({
                    "name": "Fallback Product",
                    "attributes": {},
                    "created_at": datetime.now().isoformat()
                })
            }
        ]

    def save_to_csv(self, results: List[Dict], filename: str = None) -> str:
        """Save results to CSV file."""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"product_export_{timestamp}.csv"
        
        try:
            df = pd.DataFrame(results)
            df.to_csv(filename, index=False)
            logger.info(f"Saved {len(results)} records to {filename}")
            return filename
        except Exception as e:
            logger.error(f"Error saving to CSV: {e}")
            return None

    def run(self) -> bool:
        """Main execution function implementing the complete workflow."""
        logger.info("Starting product data fetch process")

        # Step 1: Initialize database
        if not self.initialize_database():
            logger.error("Failed to initialize database")
            return False

        # Step 2: Extract SKUs from link check CSV files
        logger.info("Step 1: Extracting SKUs from link check CSV files")
        extracted_skus = self.extract_skus_from_csv_files()

        if not extracted_skus:
            logger.warning("No SKUs extracted from CSV files, using fallback data")
            results = self.create_fallback_data()
        else:
            # Step 3: Store SKUs in database with deduplication
            logger.info("Step 2: Storing SKUs in database")
            stored_count = self.store_skus_in_database(extracted_skus)
            logger.info(f"Stored {stored_count} new SKUs in database")

            # Step 4: Fetch product data from API
            results = []
            if self.auth_token:
                logger.info("Step 3: Fetching product data from CommerceTools API")
                api_results = self.fetch_products_from_api()
                if api_results:
                    results = api_results
                else:
                    logger.warning("API fetch failed, creating fallback data")
                    results = self.create_fallback_data()
            else:
                logger.info("No auth token available, creating fallback data from database")
                # Create results from database SKUs
                db_products = self.get_products_from_database()
                for product in db_products[:self.max_products]:
                    results.append({
                        "SKU": product["sku"],
                        "ID": f"db-{product['id']}",
                        "DETAIL": json.dumps({
                            "status": "from_database",
                            "message": "No API access, using database data",
                            "details": product["details"],
                            "processed_at": datetime.now().isoformat()
                        })
                    })

                if not results:
                    results = self.create_fallback_data()

        # Step 5: Save to CSV with timestamp
        logger.info("Step 4: Generating CSV export")
        filename = self.save_to_csv(results)
        if filename:
            logger.info(f"Product export completed successfully: {filename}")
            logger.info(f"Total products exported: {len(results)}")

            # Log summary statistics
            if results:
                statuses = {}
                for result in results:
                    try:
                        detail = json.loads(result.get('DETAIL', '{}'))
                        status = detail.get('status', 'unknown')
                        statuses[status] = statuses.get(status, 0) + 1
                    except:
                        statuses['parse_error'] = statuses.get('parse_error', 0) + 1

                logger.info("Export summary:")
                for status, count in statuses.items():
                    logger.info(f"  {status}: {count} products")

            return True
        else:
            logger.error("Product export failed")
            return False

def main():
    """Main entry point."""
    try:
        fetcher = ProductDataFetcher()
        success = fetcher.run()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
