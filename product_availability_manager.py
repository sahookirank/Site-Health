#!/usr/bin/env python3
"""
Product Availability Manager
Handles database operations and API integrations for CommerceTool product data.
"""

import sqlite3
import json
import re
import requests
import pandas as pd
from typing import List, Dict, Optional, Tuple
import logging
from datetime import datetime
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ProductAvailabilityManager:
    def __init__(self, db_path: str = "product_availability.db"):
        self.db_path = db_path
        self.base_url = "https://mc-api.australia-southeast1.gcp.commercetools.com"
        self.search_endpoint = f"{self.base_url}/proxy/pim-search/kmart-production/search/products"
        self.graphql_endpoint = f"{self.base_url}/graphql"
        
        # Headers for API requests (will need to be updated with valid tokens)
        self.search_headers = {
            "accept": "application/json",
            "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
            "content-type": "application/json",
            "origin": "https://mc.australia-southeast1.gcp.commercetools.com",
            "x-application-id": "__internal:products",
            "x-project-key": "kmart-production",
            "x-user-agent": "@commercetools/sdk-client Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        
        self.graphql_headers = {
            "accept": "application/json",
            "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
            "content-type": "application/json",
            "origin": "https://mc.australia-southeast1.gcp.commercetools.com",
            "x-application-id": "__internal:products",
            "x-graphql-operation-name": "GeneralInfoTabQuery",
            "x-graphql-target": "ctp",
            "x-project-key": "kmart-production",
            "x-user-agent": "apollo-client Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        
        # Initialize session and attach cookie-based auth if provided
        self.session = requests.Session()
        raw_cookie = os.getenv("COMMERCETOOL_AUTH_TOKEN", "")
        if raw_cookie:
            # Use provided cookie string verbatim to preserve escape characters
            self.session.headers.update({"Cookie": raw_cookie})
            logger.info("COMMERCETOOL_AUTH_TOKEN loaded from environment and applied as Cookie header")
        else:
            logger.warning("COMMERCETOOL_AUTH_TOKEN environment variable not set; CommerceTool requests may fail")
        
        self.init_database()
    
    def init_database(self):
        """Initialize the database and create the products-in-links table."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create the products-in-links table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS "products-in-links" (
                    ID INTEGER PRIMARY KEY AUTOINCREMENT,
                    SKU TEXT UNIQUE NOT NULL,
                    DETAILS TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create index on SKU for faster lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_sku ON "products-in-links" (SKU)
            """)
            
            conn.commit()
            conn.close()
            logger.info(f"Database initialized successfully at {self.db_path}")
            
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise
    
    def extract_product_ids_from_csv(self, csv_path: str) -> List[str]:
        """Extract product IDs from broken links in the CSV file."""
        product_ids = []
        
        try:
            df = pd.read_csv(csv_path, encoding='utf-8', encoding_errors='replace')
            
            # Look for URL column (might be named differently)
            url_columns = [col for col in df.columns if 'url' in col.lower() or 'link' in col.lower()]
            
            if not url_columns:
                logger.warning("No URL column found in CSV. Looking for product IDs in all text columns.")
                # Search all columns for product IDs
                for col in df.columns:
                    if df[col].dtype == 'object':  # Text columns
                        for value in df[col].dropna():
                            ids = self.extract_product_id_from_url(str(value))
                            product_ids.extend(ids)
            else:
                # Extract from URL columns
                for col in url_columns:
                    for url in df[col].dropna():
                        ids = self.extract_product_id_from_url(str(url))
                        product_ids.extend(ids)
            
            # Remove duplicates and return
            unique_ids = list(set(product_ids))
            logger.info(f"Extracted {len(unique_ids)} unique product IDs from {csv_path}")
            return unique_ids
            
        except Exception as e:
            logger.error(f"Error reading CSV file {csv_path}: {e}")
            return []
    
    def extract_product_id_from_url(self, url: str) -> List[str]:
        """Extract product ID from Kmart URL."""
        # Pattern to match Kmart product URLs with IDs at the end
        # Example: https://www.kmart.com.au/product/luxe-round-rug-blush-180cm-42866671/
        patterns = [
            r'kmart\.com\.au/product/[^/]+-([0-9]{8,})/?',  # Standard product URL
            r'kmart\.co\.nz/product/[^/]+-([0-9]{8,})/?',   # NZ product URL
            r'/([0-9]{8,})/?$',  # Any URL ending with 8+ digits
            r'product[^0-9]*([0-9]{8,})',  # Product followed by 8+ digits
        ]
        
        product_ids = []
        for pattern in patterns:
            matches = re.findall(pattern, url, re.IGNORECASE)
            product_ids.extend(matches)
        
        return product_ids
    
    def search_products(self, product_id: str) -> Optional[Dict]:
        """Search for products using CommerceTool-Search API."""
        search_payload = {
            "limit": 20,
            "offset": 0,
            "query": {
                "or": [
                    {
                        "fullText": {
                            "field": "name",
                            "language": "en-AU",
                            "value": product_id
                        }
                    },
                    {
                        "fullText": {
                            "field": "description",
                            "language": "en-AU",
                            "value": product_id
                        }
                    },
                    {
                        "fullText": {
                            "field": "slug",
                            "language": "en-AU",
                            "value": product_id
                        }
                    }
                ]
            },
            "enableTiebreaker": False
        }
        
        try:
            response = self.session.post(
                self.search_endpoint,
                headers=self.search_headers,
                json=search_payload,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Search API returned status {response.status_code} for product ID {product_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error searching for product {product_id}: {e}")
            return None
    
    def get_product_attributes(self, product_id: str) -> Optional[Dict]:
        """Get detailed product attributes using Product-Attributes API."""
        graphql_query = """
        query GeneralInfoTabQuery($productId: String, $isProductAttributeEnabled: Boolean!, $enableLocaleLabelOptimization: Boolean!, $locale: Locale!) {
          product(id: $productId) {
            id
            ...ProductTypeFragment
            createdAt
            lastModifiedAt
            version
            key
            priceMode
            taxCategory {
              id
              name
              key
              __typename
            }
            masterData {
              staged {
                nameAllLocales {
                  locale
                  value
                  __typename
                }
                descriptionAllLocales {
                  locale
                  value
                  __typename
                }
                categories {
                  ...CurrentCategoryFragment
                  ancestors {
                    ...CurrentCategoryFragment
                    __typename
                  }
                  __typename
                }
                masterVariant {
                  attributesRaw {
                    name
                    value
                    __typename
                  }
                  __typename
                }
                attributesRaw {
                  name
                  value
                  __typename
                }
                __typename
              }
              __typename
            }
            __typename
          }
        }
        
        fragment ProductTypeFragment on Product {
          productType {
            id
            name
            attributeDefinitions {
              results {
                attributeConstraint
                level @include(if: $isProductAttributeEnabled)
                isSearchable
                labelByLocale: label(locale: $locale) @include(if: $enableLocaleLabelOptimization)
                labelAllLocales @skip(if: $enableLocaleLabelOptimization) {
                  locale
                  value
                  __typename
                }
                inputHint
                inputTipAllLocales {
                  locale
                  value
                  __typename
                }
                isRequired
                name
                type {
                  name
                  __typename
                }
                __typename
              }
              __typename
            }
            __typename
          }
          __typename
        }
        
        fragment CurrentCategoryFragment on Category {
          id
          nameAllLocales {
            locale
            value
            __typename
          }
          __typename
        }
        """
        
        variables = {
            "productId": product_id,
            "isProductAttributeEnabled": True,
            "locale": "en-AU",
            "enableLocaleLabelOptimization": False
        }
        
        payload = {
            "operationName": "GeneralInfoTabQuery",
            "variables": variables,
            "query": graphql_query
        }
        
        try:
            response = self.session.post(
                self.graphql_endpoint,
                headers=self.graphql_headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"GraphQL API returned status {response.status_code} for product ID {product_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting product attributes for {product_id}: {e}")
            return None
    
    def store_product_data(self, sku: str, details: Dict) -> bool:
        """Store product data in the database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            details_json = json.dumps(details, indent=2)
            
            # Insert or update product data
            cursor.execute("""
                INSERT OR REPLACE INTO "products-in-links" (SKU, DETAILS, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (sku, details_json))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Stored product data for SKU: {sku}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing product data for SKU {sku}: {e}")
            return False
    
    def get_all_products(self) -> List[Dict]:
        """Retrieve all products from the database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT ID, SKU, DETAILS, created_at, updated_at 
                FROM "products-in-links" 
                ORDER BY updated_at DESC
            """)
            
            rows = cursor.fetchall()
            conn.close()
            
            products = []
            for row in rows:
                try:
                    details = json.loads(row[2])
                except json.JSONDecodeError:
                    details = {"error": "Invalid JSON data"}
                
                products.append({
                    "id": row[0],
                    "sku": row[1],
                    "details": details,
                    "created_at": row[3],
                    "updated_at": row[4]
                })
            
            return products
            
        except Exception as e:
            logger.error(f"Error retrieving products from database: {e}")
            return []
    
    def process_csv_file(self, csv_path: str) -> Dict[str, int]:
        """Process the entire CSV file and update the database."""
        logger.info(f"Processing CSV file: {csv_path}")
        
        # Extract broken links from CSV
        broken_links = self.extract_broken_links_from_csv(csv_path)
        
        stats = {
            "total_broken_links": len(broken_links),
            "total_ids": 0,
            "successful_searches": 0,
            "successful_attributes": 0,
            "stored_products": 0
        }
        
        for i, url in enumerate(broken_links, 1):
            logger.info(f"Processing broken link {i}/{len(broken_links)}: {url}")
            
            # Extract product IDs from the broken URL
            product_ids = self.extract_product_id_from_url(url)
            stats["total_ids"] += len(product_ids)
            
            for product_id in product_ids:
                logger.info(f"Processing product ID: {product_id}")
                
                # Check if product already exists in database
                existing_product = self.get_product_by_sku(product_id)
                if existing_product:
                    logger.info(f"Product {product_id} already exists in database")
                    continue
                
                # Search for the product
                search_result = self.search_products(product_id)
                if search_result and search_result.get('hits'):
                    stats["successful_searches"] += 1
                    
                    # Get the first hit's ID
                    hit_id = search_result['hits'][0].get('id')
                    if hit_id:
                        # Get detailed attributes
                        attributes = self.get_product_attributes(hit_id)
                        if attributes:
                            stats["successful_attributes"] += 1
                            
                            # Store in database
                            combined_data = {
                                "original_sku": product_id,
                                "broken_url": url,
                                "search_result": search_result,
                                "product_attributes": attributes,
                                "processed_at": datetime.now().isoformat()
                            }
                            
                            if self.store_product_data(product_id, combined_data):
                                stats["stored_products"] += 1
        
        logger.info(f"Processing complete. Stats: {stats}")
        return stats
    
    def extract_broken_links_from_csv(self, csv_path: str) -> List[str]:
        """Extract broken links (non-200 status codes or empty status) from CSV file."""
        broken_links = []

        try:
            df = pd.read_csv(csv_path, encoding='utf-8', encoding_errors='replace')

            # Filter for broken links (non-200 status codes, empty status, or null status)
            broken_df = df[
                (df['Status'] != 200.0) &
                (df['Status'].notna()) |
                (df['Status'].isna()) |
                (df['Status'] == '')
            ]

            # Extract URLs from broken links
            broken_links = broken_df['URL'].dropna().tolist()
            logger.info(f"Found {len(broken_links)} broken links (non-200 status) in {csv_path}")

        except Exception as e:
            logger.error(f"Error reading CSV file {csv_path}: {e}")

        return broken_links
    
    def get_product_by_sku(self, sku: str) -> Optional[Tuple]:
        """Retrieve a product from database by SKU."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                'SELECT ID, SKU, DETAILS, created_at, updated_at FROM "products-in-links" WHERE SKU = ?',
                (sku,)
            )
            result = cursor.fetchone()
            conn.close()
            return result
        except Exception as e:
            logger.error(f"Error retrieving product by SKU {sku}: {e}")
            return None

def main():
    """Main function for testing the ProductAvailabilityManager."""
    manager = ProductAvailabilityManager()
    
    # Test with the latest AU.csv file
    csv_path = "/Users/ksahoo/Documents/brokenlinkchecker-private/Link-Checker/latest AU.csv"
    
    if os.path.exists(csv_path):
        stats = manager.process_csv_file(csv_path)
        print(f"Processing completed with stats: {stats}")
        
        # Display some sample data
        products = manager.get_all_products()
        print(f"\nTotal products in database: {len(products)}")
        
        if products:
            print("\nSample product data:")
            for product in products[:3]:  # Show first 3 products
                print(f"SKU: {product['sku']}")
                print(f"Created: {product['created_at']}")
                print("---")
    else:
        print(f"CSV file not found: {csv_path}")

if __name__ == "__main__":
    main()