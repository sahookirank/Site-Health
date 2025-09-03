#!/usr/bin/env python3
"""
Extract the exact HTML template from test_reference_report.html and adapt it for GitHub Pages deployment workflow.
"""

import re

def extract_and_adapt_template():
    """Extract template from reference file and adapt for GitHub workflow."""
    
    # Read the reference file
    with open('test_reference_report.html', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace specific data values with template placeholders
    adaptations = [
        # Summary data replacements
        (r'Total Links Checked \(AU\): \d+', 'Total Links Checked (AU): {au_total_count}'),
        (r'Broken Links \(AU\): \d+', 'Broken Links (AU): {au_count}'),
        (r'Valid Links \(AU\): \d+', 'Valid Links (AU): {au_valid_count}'),
        (r'Total Links Checked \(NZ\): \d+', 'Total Links Checked (NZ): {nz_total_count}'),
        (r'Broken Links \(NZ\): \d+', 'Broken Links (NZ): {nz_count}'),
        (r'Valid Links \(NZ\): \d+', 'Valid Links (NZ): {nz_valid_count}'),
        
        # Table content replacements
        (r'<tbody>.*?</tbody>', '<tbody>\n                        {au_table_rows}\n                    </tbody>', re.DOTALL),
        
        # Product table replacements
        (r'Total Products: \d+', 'Total Products: {product_count}'),
    ]
    
    # Apply adaptations
    adapted_content = content
    for pattern, replacement, *flags in adaptations:
        flag = flags[0] if flags else 0
        adapted_content = re.sub(pattern, replacement, adapted_content, flags=flag)
    
    # Escape curly braces for Python format strings (except our placeholders)
    placeholders = [
        '{au_total_count}', '{au_count}', '{au_valid_count}',
        '{nz_total_count}', '{nz_count}', '{nz_valid_count}',
        '{product_count}', '{au_table_rows}', '{nz_table_rows}', '{product_table_rows}',
        '{timestamp}'
    ]
    
    # Temporarily replace placeholders with unique markers
    temp_markers = {}
    for i, placeholder in enumerate(placeholders):
        marker = f"__PLACEHOLDER_{i}__"
        temp_markers[marker] = placeholder
        adapted_content = adapted_content.replace(placeholder, marker)
    
    # Escape all remaining curly braces
    adapted_content = adapted_content.replace('{', '{{').replace('}', '}}')
    
    # Restore placeholders
    for marker, placeholder in temp_markers.items():
        adapted_content = adapted_content.replace(marker, placeholder)
    
    # Add specific table row placeholders for AU and NZ tables
    # Find AU table and replace tbody content
    au_table_pattern = r'(<table id="auLinkTable">.*?<tbody>).*?(</tbody>.*?</table>)'
    adapted_content = re.sub(au_table_pattern, r'\1\n                        {au_table_rows}\n                    \2', adapted_content, flags=re.DOTALL)
    
    # Find NZ table and replace tbody content
    nz_table_pattern = r'(<table id="nzLinkTable">.*?<tbody>).*?(</tbody>.*?</table>)'
    adapted_content = re.sub(nz_table_pattern, r'\1\n                        {nz_table_rows}\n                    \2', adapted_content, flags=re.DOTALL)
    
    # Find Product table and replace tbody content
    product_table_pattern = r'(<table class="product-table">.*?<tbody>).*?(</tbody>.*?</table>)'
    adapted_content = re.sub(product_table_pattern, r'\1\n                        {product_table_rows}\n                    \2', adapted_content, flags=re.DOTALL)
    
    return adapted_content

if __name__ == '__main__':
    template = extract_and_adapt_template()
    
    # Save the adapted template
    with open('adapted_template.html', 'w', encoding='utf-8') as f:
        f.write(template)
    
    print("✅ Template extracted and adapted successfully")
    print("📄 Saved as adapted_template.html")
    print(f"📊 Template size: {len(template):,} characters")
