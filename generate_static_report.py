#!/usr/bin/env python3
"""
Optimizely Enhanced Report Generator
Generates HTML reports with expandable JSON structure for Events, Feature Flags, and Experiments.
"""

import argparse
import datetime
import json
import os
import urllib.error
import urllib.request
import webbrowser

class OptimizelyEnhancedReportGenerator:
    def __init__(
        self,
        data_url="https://www.kmart.com.au/assets/optimizely/datafile.json",
        local_cache_path=None,
        cache_download=True,
        request_timeout=30,
    ):
        self.data_url = data_url
        self.local_cache_path = local_cache_path
        self.cache_download = cache_download
        self.request_timeout = request_timeout
        self.data = None
        
    def load_data(self):
        """Fetch Optimizely data from remote URL with optional local cache fallback."""
        fetch_error = None
        try:
            print(f"Fetching Optimizely data from {self.data_url} ...")
            req = urllib.request.Request(
                self.data_url,
                headers={
                    "User-Agent": "OptimizelyEnhancedReport/1.0 (+https://github.com/)",
                    "Accept": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=self.request_timeout) as response:
                if response.status != 200:
                    raise urllib.error.HTTPError(
                        self.data_url, response.status, response.reason, response.headers, None
                    )
                payload = response.read().decode("utf-8")
                self.data = json.loads(payload)
            print("Successfully fetched latest Optimizely data.")
            if self.local_cache_path and self.cache_download:
                try:
                    with open(self.local_cache_path, "w", encoding="utf-8") as cache_file:
                        json.dump(self.data, cache_file, ensure_ascii=False, indent=2)
                    print(f"Cached Optimizely data to {self.local_cache_path}")
                except OSError as cache_err:
                    print(f"Warning: Failed to write cache file {self.local_cache_path}: {cache_err}")
            return True
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError, json.JSONDecodeError) as err:
            fetch_error = err
            print(f"Warning: Unable to fetch data from {self.data_url}: {err}")
        
        if self.local_cache_path and os.path.exists(self.local_cache_path):
            try:
                with open(self.local_cache_path, "r", encoding="utf-8") as local_file:
                    self.data = json.load(local_file)
                print(f"Loaded Optimizely data from local cache: {self.local_cache_path}")
                return True
            except (OSError, json.JSONDecodeError) as cache_err:
                print(f"Error reading local cache {self.local_cache_path}: {cache_err}")
        
        if fetch_error:
            print("Error: Failed to retrieve Optimizely data and no valid local cache is available.")
            print(f"Last error: {fetch_error}")
        else:
            print("Error: No Optimizely data could be loaded.")
        return False
    
    def generate_expandable_json_tree(self, data, prefix="", level=0):
        """Generate expandable JSON tree structure"""
        if level > 5:  # Prevent infinite recursion
            return f'<span class="json-value">{str(data)[:100]}...</span>'
        
        if isinstance(data, dict):
            if not data:
                return '<span class="json-value">{}</span>'
            
            items = []
            for key, value in data.items():
                unique_id = f"{prefix}_{key}_{level}_{hash(str(value)) % 10000}"
                if isinstance(value, (dict, list)) and value:
                    items.append(f'''
                        <div class="json-item">
                            <span class="json-key" onclick="toggleJsonNode('{unique_id}')">
                                <i class="expand-icon">▶</i> "{key}":
                            </span>
                            <div id="{unique_id}" class="json-children collapsed">
                                {self.generate_expandable_json_tree(value, unique_id, level + 1)}
                            </div>
                        </div>
                    ''')
                else:
                    value_str = json.dumps(value) if not isinstance(value, str) else f'"{value}"'
                    items.append(f'''
                        <div class="json-item">
                            <span class="json-key">"{key}":</span>
                            <span class="json-value">{value_str}</span>
                        </div>
                    ''')
            
            return f'<div class="json-object">{{\n{"".join(items)}\n}}</div>'
        
        elif isinstance(data, list):
            if not data:
                return '<span class="json-value">[]</span>'
            
            items = []
            for i, item in enumerate(data):
                unique_id = f"{prefix}_{i}_{level}_{hash(str(item)) % 10000}"
                if isinstance(item, (dict, list)) and item:
                    items.append(f'''
                        <div class="json-item">
                            <span class="json-key" onclick="toggleJsonNode('{unique_id}')">
                                <i class="expand-icon">▶</i> [{i}]:
                            </span>
                            <div id="{unique_id}" class="json-children collapsed">
                                {self.generate_expandable_json_tree(item, unique_id, level + 1)}
                            </div>
                        </div>
                    ''')
                else:
                    value_str = json.dumps(item) if not isinstance(item, str) else f'"{item}"'
                    items.append(f'''
                        <div class="json-item">
                            <span class="json-key">[{i}]:</span>
                            <span class="json-value">{value_str}</span>
                        </div>
                    ''')
            
            return f'<div class="json-array">[\n{"".join(items)}\n]</div>'
        
        else:
            return f'<span class="json-value">{json.dumps(data)}</span>'
    
    def generate_data_section_html(self, data, section_name):
        """Generate HTML for Events, Feature Flags, and Experiments only"""
        section_prefix = ''.join(ch if ch.isalnum() else '_' for ch in section_name.lower())

        if not data:
            return f'''
                <div class="error">
                    <h3>Error Loading {section_name.upper()} Data</h3>
                    <p>No data available for this section.</p>
                </div>
            '''
        
        html = f'''
            <div class="data-section">
                <h2 class="section-title">Optimizely Configuration - {section_name.upper()}</h2>
                <div class="info-grid">
                    <div class="info-card">
                        <div class="info-label">Account ID</div>
                        <div class="info-value">{data.get('accountId', 'N/A')}</div>
                    </div>
                    <div class="info-card">
                        <div class="info-label">Project ID</div>
                        <div class="info-value">{data.get('projectId', 'N/A')}</div>
                    </div>
                    <div class="info-card">
                        <div class="info-label">Revision</div>
                        <div class="info-value">{data.get('revision', 'N/A')}</div>
                    </div>
                    <div class="info-card">
                        <div class="info-label">Environment</div>
                        <div class="info-value">{data.get('environmentKey', 'N/A')}</div>
                    </div>
                </div>
            </div>
        '''
        
        # Events Section with expandable JSON
        events = data.get('events', [])
        if events:
            html += f'''
                <div class="data-section">
                    <button class="collapsible active" onclick="toggleSection(this)">Events <span class="badge">{len(events)}</span></button>
                    <div class="content active">
                        <div class="expandable-table">
            '''
            
            for i, event in enumerate(events):
                event_id = f"{section_prefix}_event_{i}"
                html += f'''
                    <div class="table-row">
                        <div class="row-header" onclick="toggleRow('{event_id}')">
                            <i class="expand-icon">▶</i>
                            <span class="row-title">Event: {event.get('key', 'N/A')} (ID: {event.get('id', 'N/A')})</span>
                        </div>
                        <div id="{event_id}" class="row-content collapsed">
                            <div class="json-container">
                                {self.generate_expandable_json_tree(event, f"{section_prefix}_event_{i}")}
                            </div>
                        </div>
                    </div>
                '''
            
            html += '''
                        </div>
                    </div>
                </div>
            '''
        
        # Feature Flags Section with expandable JSON
        feature_flags = data.get('featureFlags', [])
        if feature_flags:
            html += f'''
                <div class="data-section">
                    <button class="collapsible active" onclick="toggleSection(this)">Feature Flags <span class="badge">{len(feature_flags)}</span></button>
                    <div class="content active">
                        <div class="expandable-table">
            '''
            
            for i, flag in enumerate(feature_flags):
                flag_id = f"{section_prefix}_flag_{i}"
                html += f'''
                    <div class="table-row">
                        <div class="row-header" onclick="toggleRow('{flag_id}')">
                            <i class="expand-icon">▶</i>
                            <span class="row-title">Feature Flag: {flag.get('key', 'N/A')} (ID: {flag.get('id', 'N/A')})</span>
                        </div>
                        <div id="{flag_id}" class="row-content collapsed">
                            <div class="json-container">
                                {self.generate_expandable_json_tree(flag, f"{section_prefix}_flag_{i}")}
                            </div>
                        </div>
                    </div>
                '''
            
            html += '''
                        </div>
                    </div>
                </div>
            '''
        
        # Experiments Section with expandable JSON
        experiments = data.get('experiments', [])
        if experiments:
            html += f'''
                <div class="data-section">
                    <button class="collapsible active" onclick="toggleSection(this)">Experiments <span class="badge">{len(experiments)}</span></button>
                    <div class="content active">
                        <div class="expandable-table">
            '''
            
            for i, exp in enumerate(experiments):
                exp_id = f"{section_prefix}_exp_{i}"
                html += f'''
                    <div class="table-row">
                        <div class="row-header" onclick="toggleRow('{exp_id}')">
                            <i class="expand-icon">▶</i>
                            <span class="row-title">Experiment: {exp.get('key', 'N/A')} (ID: {exp.get('id', 'N/A')})</span>
                        </div>
                        <div id="{exp_id}" class="row-content collapsed">
                            <div class="json-container">
                                {self.generate_expandable_json_tree(exp, f"{section_prefix}_exp_{i}")}
                            </div>
                        </div>
                    </div>
                '''
            
            html += '''
                        </div>
                    </div>
                </div>
            '''
        
        return html
    
    def generate_html_report(self):
        """Generate complete HTML report with enhanced structure"""
        print("Generating enhanced HTML report...")
        
        if not self.load_data():
            return None
        
        # Generate tab contents
        tab_contents = {
            'au': self.generate_data_section_html(self.data, 'au'),
            'au-new': self.generate_data_section_html(self.data, 'au-new'),
            'nz': self.generate_data_section_html(self.data, 'nz'),
            'nz-new': self.generate_data_section_html(self.data, 'nz-new')
        }
        
        # Generate timestamp
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        html_template = f'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Optimizely Enhanced Report - Kmart</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
            overflow: hidden;
        }}

        .header {{
            background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}

        .header h1 {{
            font-size: 2.5rem;
            margin-bottom: 10px;
            font-weight: 300;
        }}

        .header p {{
            font-size: 1.1rem;
            opacity: 0.9;
        }}

        .timestamp {{
            font-size: 0.9rem;
            opacity: 0.8;
            margin-top: 10px;
        }}

        .tabs {{
            display: flex;
            background: #f8f9fa;
            border-bottom: 1px solid #dee2e6;
        }}

        .tab {{
            flex: 1;
            padding: 20px;
            text-align: center;
            background: #f8f9fa;
            border: none;
            cursor: pointer;
            font-size: 1.1rem;
            font-weight: 500;
            color: #6c757d;
            transition: all 0.3s ease;
            position: relative;
        }}

        .tab:hover {{
            background: #e9ecef;
            color: #495057;
        }}

        .tab.active {{
            background: white;
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
        }}

        .tab-content {{
            display: none;
            padding: 30px;
            min-height: 600px;
        }}

        .tab-content.active {{
            display: block;
        }}

        .data-section {{
            margin-bottom: 30px;
        }}

        .section-title {{
            font-size: 1.5rem;
            color: #2c3e50;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #3498db;
            display: flex;
            align-items: center;
        }}

        .section-title::before {{
            content: '';
            width: 4px;
            height: 20px;
            background: #3498db;
            margin-right: 10px;
        }}

        .info-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }}

        .info-card {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #3498db;
        }}

        .info-label {{
            font-weight: 600;
            color: #495057;
            margin-bottom: 5px;
        }}

        .info-value {{
            color: #6c757d;
            font-family: 'Courier New', monospace;
        }}

        .badge {{
            display: inline-block;
            padding: 4px 8px;
            background: #3498db;
            color: white;
            border-radius: 12px;
            font-size: 0.8rem;
            font-weight: 500;
        }}

        .collapsible {{
            background: #3498db;
            color: white;
            cursor: pointer;
            padding: 15px;
            width: 100%;
            border: none;
            text-align: left;
            outline: none;
            font-size: 1rem;
            border-radius: 8px;
            margin-bottom: 10px;
            transition: background 0.3s ease;
        }}

        .collapsible:hover {{
            background: #2980b9;
        }}

        .collapsible.active {{
            background: #2980b9;
        }}

        .content {{
            padding: 0 15px;
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.3s ease-out;
            background: #f8f9fa;
            border-radius: 0 0 8px 8px;
        }}

        .content.active {{
            max-height: none;
            padding: 15px;
        }}

        .expandable-table {{
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
        }}

        .table-row {{
            border-bottom: 1px solid #dee2e6;
        }}

        .table-row:last-child {{
            border-bottom: none;
        }}

        .row-header {{
            padding: 15px 20px;
            background: #f8f9fa;
            cursor: pointer;
            display: flex;
            align-items: center;
            transition: background 0.3s ease;
        }}

        .row-header:hover {{
            background: #e9ecef;
        }}

        .row-header.expanded {{
            background: #e3f2fd;
        }}

        .expand-icon {{
            margin-right: 10px;
            transition: transform 0.3s ease;
            font-style: normal;
        }}

        .expand-icon.expanded {{
            transform: rotate(90deg);
        }}

        .row-title {{
            font-weight: 600;
            color: #2c3e50;
        }}

        .row-content {{
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.3s ease-out;
            background: white;
        }}

        .row-content.expanded {{
            max-height: none;
            padding: 20px;
        }}

        .json-container {{
            font-family: 'Courier New', monospace;
            font-size: 0.9rem;
            background: #f8f9fa;
            padding: 15px;
            border-radius: 6px;
            border: 1px solid #dee2e6;
        }}

        .json-object, .json-array {{
            margin-left: 20px;
        }}

        .json-item {{
            margin: 5px 0;
        }}

        .json-key {{
            color: #d73a49;
            font-weight: 600;
            cursor: pointer;
        }}

        .json-key:hover {{
            background: rgba(215, 58, 73, 0.1);
            border-radius: 3px;
        }}

        .json-value {{
            color: #032f62;
            margin-left: 10px;
        }}

        .json-children {{
            margin-left: 20px;
            margin-top: 5px;
        }}

        .json-children.collapsed {{
            display: none;
        }}

        .error {{
            background: #f8d7da;
            color: #721c24;
            padding: 20px;
            border-radius: 8px;
            border: 1px solid #f5c6cb;
            margin: 20px 0;
        }}

        .note {{
            background: #d1ecf1;
            color: #0c5460;
            padding: 15px;
            border-radius: 8px;
            border: 1px solid #bee5eb;
            margin: 20px 0;
            font-size: 0.9rem;
        }}

        .search-container {{
            background: #f8f9fa;
            padding: 20px 30px;
            border-bottom: 1px solid #dee2e6;
        }}

        .search-box {{
            position: relative;
            max-width: 600px;
            margin: 0 auto;
        }}

        #searchInput {{
            width: 100%;
            padding: 12px 45px 12px 15px;
            font-size: 1rem;
            border: 2px solid #dee2e6;
            border-radius: 25px;
            outline: none;
            transition: border-color 0.3s ease, box-shadow 0.3s ease;
        }}

        #searchInput:focus {{
            border-color: #3498db;
            box-shadow: 0 0 0 3px rgba(52, 152, 219, 0.1);
        }}

        .search-clear {{
            position: absolute;
            right: 10px;
            top: 50%;
            transform: translateY(-50%);
            background: #6c757d;
            color: white;
            border: none;
            border-radius: 50%;
            width: 25px;
            height: 25px;
            cursor: pointer;
            font-size: 0.8rem;
            display: none;
            transition: background 0.3s ease;
        }}

        .search-clear:hover {{
            background: #495057;
        }}

        .search-clear.visible {{
            display: block;
        }}

        .table-row.hidden {{
            display: none;
        }}

        .no-results {{
            text-align: center;
            padding: 40px 20px;
            color: #6c757d;
            font-style: italic;
        }}

        @media (max-width: 768px) {{
            .tabs {{
                flex-direction: column;
            }}
            
            .header h1 {{
                font-size: 2rem;
            }}
            
            .tab-content {{
                padding: 20px;
            }}
            
            .info-grid {{
                grid-template-columns: 1fr;
            }}
            
            .json-object, .json-array {{
                margin-left: 10px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Optimizely Enhanced Report</h1>
            <p>Kmart Australia & New Zealand - Events, Feature Flags & Experiments</p>
            <div class="timestamp">Generated on: {timestamp}</div>
        </div>
        
        <div class="search-container">
            <div class="search-box">
                <input type="text" id="searchInput" placeholder="Search Events, Feature Flags, and Experiments..." onkeyup="filterData()">
                <button class="search-clear" onclick="clearSearch()" title="Clear search">✕</button>
            </div>
        </div>
        
        <div class="tabs">
            <button class="tab active" onclick="openTab(event, 'au')">AU</button>
            <button class="tab" onclick="openTab(event, 'au-new')">AU-NEW</button>
            <button class="tab" onclick="openTab(event, 'nz')">NZ</button>
            <button class="tab" onclick="openTab(event, 'nz-new')">NZ-NEW</button>
        </div>
        
        <div id="au" class="tab-content active">
            {tab_contents.get('au', '<div class="error">Failed to load AU data</div>')}
        </div>
        
        <div id="au-new" class="tab-content">
            {tab_contents.get('au-new', '<div class="error">Failed to load AU-NEW data</div>')}
        </div>
        
        <div id="nz" class="tab-content">
            {tab_contents.get('nz', '<div class="error">Failed to load NZ data</div>')}
        </div>
        
        <div id="nz-new" class="tab-content">
            {tab_contents.get('nz-new', '<div class="error">Failed to load NZ-NEW data</div>')}
        </div>
        
    </div>

    <script>
        function openTab(evt, tabName) {{
            const tabContents = document.getElementsByClassName('tab-content');
            const tabs = document.getElementsByClassName('tab');
            
            for (let i = 0; i < tabContents.length; i++) {{
                tabContents[i].classList.remove('active');
            }}
            
            for (let i = 0; i < tabs.length; i++) {{
                tabs[i].classList.remove('active');
            }}
            
            document.getElementById(tabName).classList.add('active');
            evt.currentTarget.classList.add('active');
        }}

        function toggleSection(element) {{
            element.classList.toggle('active');
            const content = element.nextElementSibling;
            content.classList.toggle('active');
        }}

        function toggleRow(rowId) {{
            const content = document.getElementById(rowId);
            const header = content.previousElementSibling;
            const icon = header.querySelector('.expand-icon');
            
            if (content.classList.contains('expanded')) {{
                content.classList.remove('expanded');
                header.classList.remove('expanded');
                icon.classList.remove('expanded');
            }} else {{
                content.classList.add('expanded');
                header.classList.add('expanded');
                icon.classList.add('expanded');
            }}
        }}

        function toggleJsonNode(nodeId) {{
            const node = document.getElementById(nodeId);
            const icon = event.target.closest('.json-key').querySelector('.expand-icon');
            
            if (node.classList.contains('collapsed')) {{
                node.classList.remove('collapsed');
                icon.textContent = '▼';
            }} else {{
                node.classList.add('collapsed');
                icon.textContent = '▶';
            }}
        }}

        function filterData() {{
            const searchTerm = document.getElementById('searchInput').value.toLowerCase();
            const clearButton = document.querySelector('.search-clear');
            
            // Show/hide clear button
            if (searchTerm.length > 0) {{
                clearButton.classList.add('visible');
            }} else {{
                clearButton.classList.remove('visible');
            }}
            
            // Get all table rows across all tabs
            const allRows = document.querySelectorAll('.table-row');
            let hasVisibleResults = false;
            
            allRows.forEach(row => {{
                const title = row.querySelector('.row-title');
                if (title) {{
                    const titleText = title.textContent.toLowerCase();
                    if (searchTerm === '' || titleText.includes(searchTerm)) {{
                        row.classList.remove('hidden');
                        hasVisibleResults = true;
                    }} else {{
                        row.classList.add('hidden');
                    }}
                }}
            }});
            
            // Handle no results message
            const tabContents = document.querySelectorAll('.tab-content');
            tabContents.forEach(tabContent => {{
                const expandableTables = tabContent.querySelectorAll('.expandable-table');
                expandableTables.forEach(table => {{
                    const visibleRows = table.querySelectorAll('.table-row:not(.hidden)');
                    let noResultsDiv = table.querySelector('.no-results');
                    
                    if (searchTerm !== '' && visibleRows.length === 0) {{
                        if (!noResultsDiv) {{
                            noResultsDiv = document.createElement('div');
                            noResultsDiv.className = 'no-results';
                            noResultsDiv.textContent = 'No results found for "' + document.getElementById('searchInput').value + '"';
                            table.appendChild(noResultsDiv);
                        }}
                    }} else if (noResultsDiv) {{
                        noResultsDiv.remove();
                    }}
                }});
            }});
        }}

        function clearSearch() {{
            document.getElementById('searchInput').value = '';
            filterData();
            document.getElementById('searchInput').focus();
        }}

        // Add event listener for Enter key
        document.addEventListener('DOMContentLoaded', function() {{
            document.getElementById('searchInput').addEventListener('keypress', function(e) {{
                if (e.key === 'Enter') {{
                    e.preventDefault();
                }}
            }});
        }});
    </script>
</body>
</html>
        '''
        
        return html_template
    
    def save_report(self, filename="optimizely_enhanced_report.html"):
        """Save the generated report to a file"""
        html_content = self.generate_html_report()
        
        if html_content is None:
            print("Failed to generate report due to data loading issues.")
            return None
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"Enhanced report saved as: {filename}")
        return filename

def main():
    """Main function to run the enhanced report generator"""
    print("Optimizely Enhanced Data Report Generator")
    print("=" * 50)

    parser = argparse.ArgumentParser(description="Generate the Optimizely enhanced HTML report.")
    parser.add_argument(
        "--data-url",
        default="https://www.kmart.com.au/assets/optimizely/datafile.json",
        help="Remote Optimizely datafile URL to fetch (default: %(default)s)",
    )
    parser.add_argument(
        "--local-backup",
        help="Optional path to a local JSON file used as fallback when fetching fails.",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable writing the downloaded data to the local backup file.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="HTTP request timeout in seconds (default: %(default)s).",
    )
    parser.add_argument(
        "--output",
        default="optimizely_enhanced_report.html",
        help="Filename for the generated HTML report (default: %(default)s).",
    )
    parser.add_argument(
        "--open-browser",
        action="store_true",
        help="Automatically open the generated report in the default browser.",
    )
    args = parser.parse_args()

    generator = OptimizelyEnhancedReportGenerator(
        data_url=args.data_url,
        local_cache_path=args.local_backup,
        cache_download=not args.no_cache,
        request_timeout=args.timeout,
    )
    
    print("\nGenerating enhanced HTML report with expandable JSON structure...")
    filename = generator.save_report(filename=args.output)
    
    if filename:
        file_path = os.path.abspath(filename)
        print(f"\nEnhanced report saved to: {file_path}")
        print("\nEnhanced report generation completed successfully!")
        print("Features:")
        print("- Focus on Events, Feature Flags, and Experiments")
        print("- Expandable rows with detailed JSON structure")
        if args.open_browser:
            print(f"\nOpening enhanced report in browser: {file_path}")
            webbrowser.open(f'file://{file_path}')
    else:
        print("\nReport generation failed.")

if __name__ == "__main__":
    main()
