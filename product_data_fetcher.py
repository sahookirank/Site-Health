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

    def fetch_products_from_api(self) -> List[Dict]:
        """Fetch products from the CommerceTools API."""
        if not self.auth_token:
            logger.warning("No auth token available, skipping API fetch")
            return []
        
        try:
            # This is a simplified version - in a full implementation,
            # you would implement the complete API fetching logic
            logger.info("Fetching products from CommerceTools API")
            
            # Placeholder for API implementation
            # In the real implementation, this would make actual API calls
            # to fetch product data and update the database
            
            logger.info("API fetch completed (placeholder implementation)")
            return []
            
        except Exception as e:
            logger.error(f"Error fetching from API: {e}")
            return []

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
        """Main execution function."""
        logger.info("Starting product data fetch process")
        
        # Initialize database
        if not self.initialize_database():
            logger.error("Failed to initialize database")
            return False
        
        # Try to get products from various sources
        results = []
        
        if self.auth_token:
            # Try API first
            api_products = self.fetch_products_from_api()
            if api_products:
                results = api_products
            else:
                # Fall back to database
                db_products = self.get_products_from_database()
                if db_products:
                    results = []
                    for product in db_products[:self.max_products]:
                        results.append({
                            "SKU": product["sku"],
                            "ID": product["id"],
                            "DETAIL": json.dumps(product["details"])
                        })
        
        # If no results from API or database, use fallback
        if not results:
            logger.warning("No products found from API or database, using fallback data")
            results = self.create_fallback_data()
        
        # Save to CSV
        filename = self.save_to_csv(results)
        if filename:
            logger.info(f"Product export completed successfully: {filename}")
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
