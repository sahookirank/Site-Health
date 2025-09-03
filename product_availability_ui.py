import json
import html
import pandas as pd
import os
from datetime import datetime

def format_product_attributes(attributes_raw, is_discontinued=False, has_past_end_date=False):
    """Format product attributes for HTML display with visual indicators."""
    if not attributes_raw:
        return "<div class='no-attributes'>No attributes available</div>"
    
    formatted_attrs = []
    current_date = datetime.now().date()
    
    for attr in attributes_raw:
        attr_name = attr.get('name', 'Unknown')
        attr_value = attr.get('value', 'N/A')
        
        # Special handling for date attributes
        if attr_name in ['EndDate', 'EndDateNZ', 'StartDate', 'StartDateNZ']:
            if attr_value and attr_value != '9999-12-31':
                try:
                    date_obj = datetime.strptime(attr_value, '%Y-%m-%d').date()
                    formatted_date = date_obj.strftime('%d %b %Y')
                    
                    # Highlight past end dates in red
                    if attr_name in ['EndDate', 'EndDateNZ'] and date_obj < current_date:
                        formatted_attrs.append(
                            f"<div class='attribute-item'>"
                            f"<span class='attr-name'><strong>{attr_name}:</strong></span> "
                            f"<span class='attr-value past-end-date' style='background-color: red; color: white; padding: 2px 4px; border-radius: 3px;'>{formatted_date}</span>"
                            f"</div>"
                        )
                    else:
                        formatted_attrs.append(
                            f"<div class='attribute-item'>"
                            f"<span class='attr-name'><strong>{attr_name}:</strong></span> "
                            f"<span class='attr-value'>{formatted_date}</span>"
                            f"</div>"
                        )
                except ValueError:
                    # If date parsing fails, show original value
                    formatted_attrs.append(
                        f"<div class='attribute-item'>"
                        f"<span class='attr-name'><strong>{attr_name}:</strong></span> "
                        f"<span class='attr-value'>{attr_value}</span>"
                        f"</div>"
                    )
            else:
                # Handle null or default dates
                display_value = "No end date" if attr_value == '9999-12-31' else attr_value
                formatted_attrs.append(
                    f"<div class='attribute-item'>"
                    f"<span class='attr-name'><strong>{attr_name}:</strong></span> "
                    f"<span class='attr-value'>{display_value}</span>"
                    f"</div>"
                )
        else:
            # Regular attributes
            formatted_attrs.append(
                f"<div class='attribute-item'>"
                f"<span class='attr-name'><strong>{attr_name}:</strong></span> "
                f"<span class='attr-value'>{html.escape(str(attr_value))}</span>"
                f"</div>"
            )
    
    return "<div class='attributes-container'>" + "".join(formatted_attrs) + "</div>"

def load_product_csv_data(csv_path=None):
    """Load product data from CSV file."""
    if csv_path and os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path)
            return df
        except Exception as e:
            print(f"Error reading {csv_path}: {e}")

    # Fallback to default files
    csv_files = [
        'product_export_20250902_055919.csv',
        'product_export.csv'
    ]

    for csv_file in csv_files:
        if os.path.exists(csv_file):
            try:
                df = pd.read_csv(csv_file)
                return df
            except Exception as e:
                print(f"Error reading {csv_file}: {e}")
                continue

    return None

def generate_product_availability_html(csv_path=None):
    """Generate HTML content for the Product Availability tab."""
    try:
        # Load CSV data instead of database data
        df = load_product_csv_data(csv_path)
        
        if df is None or df.empty:
            return """
            <div class="summary-container">
                <span class="summary-item">📦 Total Products: 0</span>
                <span class="summary-item">ℹ️ No product data available</span>
            </div>
            <div class="card">
                <p>No product availability data found. Please run the product extraction process first.</p>
            </div>
            """
        
        # Convert CSV data to product list format
        products = []
        current_date = datetime.now().date()
        
        for _, row in df.iterrows():
            try:
                detail_json = json.loads(row['DETAIL'])
                attributes = detail_json.get('attributes', {})
                
                # Check if product is discontinued based on EndDate
                is_discontinued = False
                end_date_au = attributes.get('EndDate')
                end_date_nz = attributes.get('EndDateNZ')
                
                if end_date_au and end_date_au != '9999-12-31':
                    try:
                        end_date_au_parsed = datetime.strptime(end_date_au, '%Y-%m-%d').date()
                        if end_date_au_parsed < current_date:
                            is_discontinued = True
                    except ValueError:
                        pass
                        
                if end_date_nz and end_date_nz != '9999-12-31':
                    try:
                        end_date_nz_parsed = datetime.strptime(end_date_nz, '%Y-%m-%d').date()
                        if end_date_nz_parsed < current_date:
                            is_discontinued = True
                    except ValueError:
                        pass
                
                # Override product type if discontinued
                if is_discontinued:
                    detail_json['product_type'] = 'DISCONTINUED'
                
                product = {
                    'sku': row['SKU'],
                    'id': row['ID'],
                    'details': detail_json,
                    'is_discontinued': is_discontinued
                }
                products.append(product)
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Error processing row: {e}")
                continue
        
        total_products = len(products)
        
        # Generate expandable product rows for all products
        def generate_product_rows(products):
            if not products:
                return "<tr><td colspan='4'>No products available</td></tr>"
            
            rows = []
            current_date = datetime.now().date()
            
            for i, product in enumerate(products):
                sku = product.get('sku', 'Unknown SKU')
                product_id = product.get('id', 'Unknown ID')
                details_obj = product.get('details', {})
                is_discontinued = product.get('is_discontinued', False)
                
                # Extract product information from details
                product_name = details_obj.get('name', 'Unknown Product')
                product_type = details_obj.get('product_type', 'Unknown Type')
                attributes = details_obj.get('attributes', {})
                
                # Convert attributes to the format expected by format_product_attributes
                attributes_raw = []
                for attr_name, attr_value in attributes.items():
                    attributes_raw.append({
                        'name': attr_name,
                        'value': attr_value
                    })
                
                # Check EndDate values for highlighting
                end_date_au = attributes.get('EndDate')
                end_date_nz = attributes.get('EndDateNZ')
                has_past_end_date = False
                
                if end_date_au and end_date_au != '9999-12-31':
                    try:
                        end_date_au_parsed = datetime.strptime(end_date_au, '%Y-%m-%d').date()
                        if end_date_au_parsed < current_date:
                            has_past_end_date = True
                    except ValueError:
                        pass
                        
                if end_date_nz and end_date_nz != '9999-12-31':
                    try:
                        end_date_nz_parsed = datetime.strptime(end_date_nz, '%Y-%m-%d').date()
                        if end_date_nz_parsed < current_date:
                            has_past_end_date = True
                    except ValueError:
                        pass
                        
                # Override product type if discontinued
                if is_discontinued or has_past_end_date:
                    product_type = 'DISCONTINUED'
                    is_discontinued = True
                
                # Format attributes with visual indicators
                formatted_attributes = format_product_attributes(attributes_raw, is_discontinued, has_past_end_date)
                
                row_id = f"product_{i}"
                
                # Apply CSS class for discontinued products
                type_class = "discontinued" if product_type == "DISCONTINUED" else ""
                
                rows.append(f"""
                <tr class="product-row" onclick="toggleProductDetails('{row_id}')">
                    <td><strong>{sku}</strong></td>
                    <td>{product_name}</td>
                    <td>
                        <span class="product-type-badge {type_class}">{product_type}</span>
                    </td>
                    <td>
                        <span class="toggle-icon" id="{row_id}_toggle">▼</span>
                    </td>
                </tr>
                <tr id="{row_id}_details" class="product-details-row" style="display: none;">
                    <td colspan="4">
                        <div class="product-details-content">
                            <h4>Product Details (SKU: {sku})</h4>
                            <div class="attributes-section">
                                {formatted_attributes}
                            </div>
                        </div>
                    </td>
                </tr>
                """)
            
            return '\n'.join(rows)
        
        product_rows = generate_product_rows(products)
        
        return f"""
        <div class="summary-container">
            <span class="summary-item">📦 Total Products: {total_products}</span>
        </div>
        
        <div class="product-availability-container">
            <div class="card">
                <h3>Product Availability</h3>
                <div class="table-container">
                    <table class="product-table">
                        <thead>
                            <tr>
                                <th>SKU</th>
                                <th>Product Name</th>
                                <th>Type</th>
                                <th>Details</th>
                            </tr>
                        </thead>
                        <tbody>
                            {product_rows}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        """
        
    except Exception as e:
        return f"""
        <div class="summary-container">
            <span class="summary-item">❌ Error loading product data</span>
        </div>
        <div class="card">
            <p>Error loading product availability data: {html.escape(str(e))}</p>
        </div>
        """

def get_product_availability_styles():
    """Return CSS styles specific to the Product Availability tab."""
    return """
            /* Product Availability Styles */
            .product-availability-container {
                margin-top: 20px;
            }
            /* Table container for responsive design */
            .table-container {
                width: 100%;
                overflow-x: auto;
                margin-top: 15px;
            }
            
            .product-table {
                width: 100%;
                min-width: 600px;
                border-collapse: collapse;
                background-color: white;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .product-table th {
                background-color: var(--brand);
                color: white;
                padding: 12px;
                text-align: left;
                font-weight: 600;
                font-size: 14px;
                white-space: nowrap;
            }
            .product-table td {
                padding: 12px;
                border-bottom: 1px solid #e5e7eb;
                vertical-align: top;
                word-wrap: break-word;
                max-width: 300px;
            }
            .product-row {
                cursor: pointer;
                transition: background-color 0.2s ease;
            }
            .product-row:hover {
                background-color: #f9fafb;
            }
            .product-details-row {
                background-color: #f8fafc;
            }
            .product-details-content {
                padding: 16px;
                border-left: 4px solid var(--brand);
                background-color: #fff;
                border-radius: 8px;
                margin: 8px;
            }
            .product-details-content h4 {
                margin: 0 0 12px 0;
                color: var(--brand);
                font-size: 16px;
            }
            .json-display {
                background-color: #f8fafc;
                border: 1px solid #e5e7eb;
                border-radius: 6px;
                padding: 12px;
                font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
                font-size: 12px;
                line-height: 1.4;
                overflow-x: auto;
                white-space: pre-wrap;
                word-wrap: break-word;
                max-height: 400px;
                overflow-y: auto;
            }
            
            /* Product Attribute Styles */
            .attributes-section {
                margin-bottom: 20px;
            }
            .attributes-container {
                background-color: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 8px;
                padding: 16px;
                max-height: 400px;
                overflow-y: auto;
            }
            .attribute-item {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 8px 12px;
                margin-bottom: 4px;
                background-color: #ffffff;
                border: 1px solid #e9ecef;
                border-radius: 4px;
                box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
            }
            .attribute-item:last-child {
                margin-bottom: 0;
            }
            .attr-name {
                color: #495057;
                min-width: 180px;
                flex-shrink: 0;
                margin-right: 12px;
            }
            .attr-value {
                color: #6c757d;
                text-align: right;
                word-break: break-word;
                flex-grow: 1;
            }
            .no-attributes {
                text-align: center;
                color: #6c757d;
                font-style: italic;
                padding: 20px;
            }
            
            /* Visual Indicators */
            .past-date {
                background-color: #fee2e2 !important;
                border-left: 4px solid #dc2626 !important;
                padding-left: 8px !important;
            }
            .past-date .attribute-value {
                color: #dc2626 !important;
                font-weight: 600 !important;
            }
            .discontinued-indicator {
                background-color: #dc2626;
                color: white;
                padding: 8px 12px;
                border-radius: 4px;
                font-weight: 600;
                text-align: center;
                margin-bottom: 12px;
                font-size: 14px;
            }
            .product-type-badge.discontinued {
                background-color: #dc2626 !important;
                color: white !important;
                font-weight: 600 !important;
            }
            .product-type-badge {
                display: inline-block;
                padding: 4px 8px;
                background-color: #e0f2fe;
                color: #0369a1;
                border-radius: 12px;
                font-size: 11px;
                font-weight: 600;
                text-transform: uppercase;
                margin-left: 8px;
            }
            .toggle-icon {
                font-size: 14px;
                margin-right: 8px;
                transition: transform 0.3s ease;
                display: inline-block;
            }
            .toggle-icon.rotated {
                transform: rotate(180deg);
            }
    """

def get_product_availability_scripts():
    """Return JavaScript functions for Product Availability tab."""
    return """
            // Product Availability JavaScript Functions
            window.toggleProductDetails = function(rowId) {
                var detailsRow = document.getElementById(rowId + '_details');
                var toggleIcon = document.getElementById(rowId + '_toggle');
                
                if (detailsRow.style.display === 'none' || detailsRow.style.display === '') {
                    detailsRow.style.display = 'table-row';
                    toggleIcon.textContent = '▲';
                    toggleIcon.classList.add('rotated');
                } else {
                    detailsRow.style.display = 'none';
                    toggleIcon.textContent = '▼';
                    toggleIcon.classList.remove('rotated');
                }
            };
            
            window.openProductRegion = function(evt, regionName) {
                var i, categoryContent, categoryTabs;
                categoryContent = document.getElementsByClassName('category-content');
                for (i = 0; i < categoryContent.length; i++) {
                    categoryContent[i].classList.remove('active');
                }
                categoryTabs = document.getElementsByClassName('category-tab');
                for (i = 0; i < categoryTabs.length; i++) {
                    categoryTabs[i].classList.remove('active');
                }
                document.getElementById(regionName).classList.add('active');
                evt.currentTarget.classList.add('active');
            };
    """