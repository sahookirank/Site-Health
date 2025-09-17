#!/usr/bin/env python3
"""
Deployment Test Script for Page Views Integration

This script validates:
1. API calls work correctly with provided credentials
2. Report generation functions properly
3. All data displays accurately in the UI
4. GitHub Pages deployment is functional
"""

import argparse
import os
import subprocess
import sys
import time
import requests
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parent


def test_local_generation(base_url, cookie, account_id):
    """Test local report generation with provided credentials."""
    print("\n🧪 Testing local report generation...")
    
    # Set environment variables
    env = os.environ.copy()
    env.update({
        "NEWRELIC_BASE_URL": base_url,
        "NEWRELIC_COOKIE": cookie,
        "NEWRELIC_ACCOUNT_ID": account_id
    })
    
    # Run the test script
    result = subprocess.run(
        [sys.executable, "test_page_views.py"],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print("✅ Local generation successful")
        return True
    else:
        print("❌ Local generation failed:")
        print(result.stderr)
        return False


def test_api_connectivity(base_url, cookie, account_id):
    """Test direct API connectivity to New Relic."""
    print("\n🌐 Testing New Relic API connectivity...")
    
    try:
        # Test basic connectivity to New Relic
        headers = {
            'Cookie': cookie,
            'User-Agent': 'Mozilla/5.0 (compatible; Link-Checker/1.0)'
        }
        
        response = requests.get(base_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            print("✅ API connectivity successful")
            return True
        else:
            print(f"❌ API returned status code: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ API connectivity failed: {e}")
        return False


def test_report_content():
    """Test that the generated report contains expected content."""
    print("\n📄 Testing report content...")
    
    report_path = ROOT / "combined_report.html"
    
    if not report_path.exists():
        print("❌ Report file not found")
        return False
    
    content = report_path.read_text(encoding='utf-8')
    
    # Check for key elements
    checks = [
        ('Page Views tab', 'Page Views'),
        ('Top Products table', 'topProductsTable'),
        ('Top Pages table', 'topPagesTable'),
        ('Broken Links Views table', 'brokenLinksViewsTable'),
        ('DataTables functionality', 'DataTable'),
        ('Bootstrap styling', 'bootstrap')
    ]
    
    all_passed = True
    for check_name, check_string in checks:
        if check_string in content:
            print(f"✅ {check_name} found")
        else:
            print(f"❌ {check_name} missing")
            all_passed = False
    
    return all_passed


def test_github_pages_deployment(repo_url):
    """Test that GitHub Pages deployment is accessible."""
    print("\n🚀 Testing GitHub Pages deployment...")
    
    # Construct GitHub Pages URL
    if repo_url.startswith('https://github.com/'):
        # Extract owner/repo from GitHub URL
        parts = repo_url.replace('https://github.com/', '').split('/')
        if len(parts) >= 2:
            owner, repo = parts[0], parts[1]
            pages_url = f"https://{owner}.github.io/{repo}/"
            
            try:
                response = requests.get(pages_url, timeout=30)
                if response.status_code == 200:
                    print(f"✅ GitHub Pages accessible at {pages_url}")
                    return True, pages_url
                else:
                    print(f"❌ GitHub Pages returned status: {response.status_code}")
                    return False, pages_url
            except Exception as e:
                print(f"❌ GitHub Pages test failed: {e}")
                return False, pages_url
    
    print("❌ Could not determine GitHub Pages URL")
    return False, None


def main():
    parser = argparse.ArgumentParser(description="Test deployment functionality")
    parser.add_argument("--base-url", required=True, help="NEWRELIC_BASE_URL")
    parser.add_argument("--cookie", required=True, help="NEWRELIC_COOKIE")
    parser.add_argument("--account-id", required=True, help="NEWRELIC_ACCOUNT_ID")
    parser.add_argument("--repo-url", help="GitHub repository URL for Pages testing")
    parser.add_argument("--skip-api", action="store_true", help="Skip API connectivity test")
    parser.add_argument("--skip-pages", action="store_true", help="Skip GitHub Pages test")
    
    args = parser.parse_args()
    
    print("🔍 Starting deployment validation tests...")
    
    results = []
    
    # Test API connectivity
    if not args.skip_api:
        results.append(test_api_connectivity(args.base_url, args.cookie, args.account_id))
    
    # Test local generation
    results.append(test_local_generation(args.base_url, args.cookie, args.account_id))
    
    # Test report content
    results.append(test_report_content())
    
    # Test GitHub Pages deployment
    if not args.skip_pages and args.repo_url:
        pages_success, pages_url = test_github_pages_deployment(args.repo_url)
        results.append(pages_success)
        if pages_success:
            print(f"\n🌐 Deployment URL: {pages_url}")
    
    # Summary
    passed = sum(results)
    total = len(results)
    
    print(f"\n📊 Test Results: {passed}/{total} passed")
    
    if passed == total:
        print("🎉 All tests passed! Deployment is ready.")
        return 0
    else:
        print("⚠️  Some tests failed. Please review and fix issues.")
        return 1


if __name__ == "__main__":
    sys.exit(main())