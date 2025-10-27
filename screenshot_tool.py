#!/usr/bin/env python3
"""
Enhanced Kmart Screenshot Tool with Login Support

This script captures screenshots of Kmart website pages in a specific sequence:

WORKFLOW:
1. Capture PUBLIC pages (before login):
   - Home page
   - Home & Living category
   - Product page (Red Stripe Ceramic Candle)
   - Clearance page
2. Click search icon on home page, then click search input field (#cio-autocomplete-0-input)
3. Login using provided credentials (passkey skip = success)
4. Capture AUTHENTICATED pages (after login):
   - Shopping bag/cart
   - Wishlist

INTEGRATION:
- Screenshots are automatically generated during GitHub Pages deployment
- Results are embedded in the main dashboard as a "Screenshots" tab
- Access via: https://your-username.github.io/Site-Health/screenshots/
- Individual screenshots: https://your-username.github.io/Site-Health/screenshots/*.jpg

IMPORTANT LOGIN NOTES:
- If passkey screen appears and "Skip for now" is clicked → LOGIN SUCCESSFUL
- No need to retry login after passkey skip
- Wait for automatic redirection after passkey skip
"""

import asyncio
import os
import random
from datetime import datetime, timedelta
from playwright.async_api import async_playwright
from pathlib import Path
from screenshot_database import ScreenshotDatabase, save_screenshot_to_db, get_image_data_url
OUTPUT_DIR = "screenshots"
# Public URLs to capture before login (only URLs that definitely work without login)
PUBLIC_URLS = [
    "https://www.kmart.com.au/",
    # Note: Category and product pages may require login - moved to authenticated if needed
]

# Authenticated URLs to capture after login (pages that may require login)
AUTHENTICATED_URLS = [
    "https://www.kmart.com.au/checkout/bag",
    "https://www.kmart.com.au/wishlist/",
    "https://www.kmart.com.au/category/home-and-living/shop-all-home-and-living/",  # May require login
    "https://www.kmart.com.au/product/red-stripe-ceramic-candle-43543175/",  # May require login
    "https://www.kmart.com.au/category/clearance/shop-all-clearance/"  # May require login
]

# Combined URLs for backward compatibility
URLS = PUBLIC_URLS + AUTHENTICATED_URLS
SCREENSHOT_OPTIONS = {
    'full_page': True,
    'type': 'jpeg',
    'quality': 80
}

# Login Configuration
LOGIN_CONFIG = {
    'enabled': True,
    'login_url': 'https://auth.kmart.com.au/u/login',
    'username': os.getenv('KMART_USERNAME'),  # Set via environment variable
    'password': os.getenv('KMART_PASSWORD'),  # Set via environment variable
    'username_field': '#username',
    'password_field': '#password',
    'login_button': 'button:has-text("Continue to password")',
    'password_submit_button': 'button:has-text("Sign in")',
    'login_success_indicator': '.account-menu, .user-menu, [data-testid="account-menu"], .dashboard, .home-page',  # Element that appears after successful login
    'passkey_skip_link': 'text="Skip for now"',
    'login_timeout': 30000,  # 30 seconds
    'max_login_attempts': 3
}

async def login_to_site(page, config):
    """Login to the website using the provided configuration."""
    if not config['enabled'] or not config['username'] or not config['password']:
        print("Login disabled or credentials not provided")
        return True

    print("Attempting to login...")

    for attempt in range(config['max_login_attempts']):
        try:
            print(f"Login attempt {attempt + 1}/{config['max_login_attempts']}")

            # Navigate to login page
            await page.goto(config['login_url'], timeout=config['login_timeout'])

            # Wait for login form to load
            await page.wait_for_load_state('networkidle', timeout=config['login_timeout'])

            # Step 1: Enter username and click "Continue to password"
            username_field = await page.query_selector(config['username_field'])
            if not username_field:
                print(f"Username field not found on attempt {attempt + 1}")
                continue

            await username_field.fill('')
            await username_field.fill(config['username'])
            await asyncio.sleep(1)

            # Click continue to password button
            continue_button = await page.query_selector(config['login_button'])
            if continue_button:
                await continue_button.click()
                await asyncio.sleep(2)
            else:
                print("Continue to password button not found")

            # Step 2: Enter password and click "Sign in"
            password_field = await page.query_selector(config['password_field'])
            if not password_field:
                print(f"Password field not found on attempt {attempt + 1}")
                continue

            await password_field.fill('')
            await password_field.fill(config['password'])
            await asyncio.sleep(1)

            # Click sign in button
            signin_button = await page.query_selector(config['password_submit_button'])
            if signin_button:
                await signin_button.click()
                await asyncio.sleep(3)
            else:
                print("Sign in button not found")

            # Step 3: Check for passkey screen and skip if present
            try:
                passkey_skip = await page.query_selector(config['passkey_skip_link'])
                if passkey_skip:
                    print("Passkey screen detected, clicking 'Skip for now' - LOGIN SUCCESSFUL!")
                    await passkey_skip.click()
                    await asyncio.sleep(5)  # Wait for redirection

                    # Check if we were redirected to success page
                    success_indicator = await page.query_selector(config['login_success_indicator'])
                    if success_indicator:
                        print("Successfully redirected after passkey skip!")
                        return True
                    else:
                        print("Login successful via passkey skip!")
                        # Additional wait for complete page load
                        await asyncio.sleep(3)
                        return True
                else:
                    print("No passkey screen detected")
            except Exception as e:
                print(f"Error checking for passkey screen: {str(e)}")

            # Step 4: Wait for complete page load and check for success
            await page.wait_for_load_state('networkidle', timeout=config['login_timeout'])

            # Check if login was successful
            success_indicator = await page.query_selector(config['login_success_indicator'])
            if success_indicator:
                print("Login successful!")
                # Additional wait for complete page load
                await asyncio.sleep(3)
                return True
            else:
                print("Login may have failed - success indicator not found")
                # Check for error messages
                error_elements = await page.query_selector_all('.error, .alert, [role="alert"], .message-error')
                for error in error_elements:
                    error_text = await error.text_content()
                    if error_text:
                        print(f"Login error: {error_text}")

        except Exception as e:
            print(f"Login attempt {attempt + 1} failed: {str(e)}")

        # Wait before retry
        if attempt < config['max_login_attempts'] - 1:
            await asyncio.sleep(3)

    print("All login attempts failed")
    return False

async def capture_search_screenshot(page):
    """Click on search icon and then click on search input field to take screenshot."""
    try:
        # First, find and click the search icon to open search overlay
        search_selectors = [
            '[titleid="icon-title-Search"]',
            '[titleid="Search"]',
            '[data-testid="search-icon"]',
            'button[aria-label*="Search"]',
            'a[aria-label*="Search"]',
            '.search-icon',
            '#search',
            'svg[titleid="icon-title-Search"]'
        ]

        search_icon = None
        for selector in search_selectors:
            search_icon = await page.query_selector(selector)
            if search_icon:
                print(f"Found search icon with selector: {selector}")
                break

        if search_icon:
            print("Found search icon, clicking to open search overlay...")
            await search_icon.click()
            await asyncio.sleep(2)

            # Now look for the specific search input field
            search_input = await page.query_selector('#cio-autocomplete-0-input')

            if search_input:
                print("Found search input field, clicking on it...")
                await search_input.click()
                await asyncio.sleep(1)

                # Wait for search overlay or page to load
                await page.wait_for_load_state('networkidle', timeout=10000)

                # Take screenshot with specific name
                filename = "home-search.jpg"
                filepath = os.path.join(OUTPUT_DIR, filename)

                await page.screenshot(
                    path=filepath,
                    full_page=True,
                    type='jpeg',
                    quality=80
                )

                print(f"Search screenshot captured: {filename}")
                # Save to database
                screenshot_db = ScreenshotDatabase()
                metadata = {
                    'original_url': 'search-overlay',
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'success': True,
                    'file_size': os.path.getsize(filepath),
                    'search_clicked': True
                }
                save_screenshot_to_db(screenshot_db, 'home-search', 'search-overlay', filename, filepath, metadata)

                return {
                    'url': 'search-overlay',
                    'filename': filename,
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'success': True
                }
            else:
                print("Search input field (#cio-autocomplete-0-input) not found")
                # Still take screenshot of whatever search overlay is visible
                filename = "home-search.jpg"
                filepath = os.path.join(OUTPUT_DIR, filename)

                await page.screenshot(
                    path=filepath,
                    full_page=True,
                    type='jpeg',
                    quality=80
                )

                print(f"Search screenshot captured (without input click): {filename}")
                # Save to database
                screenshot_db = ScreenshotDatabase()
                metadata = {
                    'original_url': 'search-overlay',
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'success': True,
                    'file_size': os.path.getsize(filepath),
                    'search_clicked': False
                }
                save_screenshot_to_db(screenshot_db, 'home-search', 'search-overlay', filename, filepath, metadata)

                return {
                    'url': 'search-overlay',
                    'filename': filename,
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'success': True
                }
        else:
            print("Search icon not found with any selector")
            return None

    except Exception as e:
        print(f"Error capturing search screenshot: {str(e)}")
        return None

async def take_screenshot(page, url, custom_name=None):
    """Take a screenshot of a webpage and save to both filesystem and database"""
    if custom_name:
        filename = custom_name
        page_name = custom_name  # Use the same name for database storage
    else:
        filename = url.replace('https://', '').replace('/', '_').replace('?', '_')
        if len(filename) > 50:  # Limit filename length
            filename = filename[:50]
        page_name = filename  # Fallback for database

    filename = f"{filename}.jpg"
    filepath = os.path.join(OUTPUT_DIR, filename)

    try:
        # Set a longer timeout and wait for the page to be fully loaded
        await page.goto(
            url=url,
            timeout=60000,
            wait_until='networkidle',
            referer='https://www.google.com/'
        )

        # Add some random delay to mimic human behavior
        await asyncio.sleep(1 + random.random() * 2)

        # Scroll the page to trigger lazy-loaded content
        await page.evaluate('''async () => {
            await new Promise(resolve => {
                let totalHeight = 0;
                const distance = 100;
                const timer = setInterval(() => {
                    const scrollHeight = document.body.scrollHeight;
                    window.scrollBy(0, distance);
                    totalHeight += distance;
                    if(totalHeight >= scrollHeight || totalHeight > 10000) {
                        clearInterval(timer);
                        resolve();
                    }
                }, 100);
            });
        }''')

        # Wait a bit after scrolling
        await asyncio.sleep(1)

        # Take screenshot of the full page with better error handling
        try:
            await page.screenshot(
                path=filepath,
                full_page=True,
                type='jpeg',
                quality=80
            )
        except Exception as e:
            # Try again with a simpler screenshot if full page fails
            await page.screenshot(path=filepath, type='jpeg', quality=80)

        # Verify the screenshot was created and has content
        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
            raise Exception("Screenshot file was not created or is empty")

        # Save to database for persistence
        screenshot_db = ScreenshotDatabase()
        metadata = {
            'original_url': url,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'success': True,
            'file_size': os.path.getsize(filepath)
        }

        # Save to database
        save_screenshot_to_db(screenshot_db, page_name, url, filename, filepath, metadata)

        return {
            'url': url,
            'filename': filename,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'success': True
        }

    except Exception as e:
        print(f"Error capturing {url}: {str(e)}")
        # Return the item with success=False to show in the UI
        return {
            'url': url,
            'filename': filename,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'success': False,
            'error': str(e)
        }

async def main():
    # Initialize database
    screenshot_db = ScreenshotDatabase()

    # Clean up old screenshots (keep last 30 days)
    screenshot_db.cleanup_old_screenshots(keep_days=30)

    # Create screenshots directory if it doesn't exist
    Path(OUTPUT_DIR).mkdir(exist_ok=True)

    async with async_playwright() as p:
        # Launch browser with additional context options to avoid detection
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox'
            ]
        )

        # Create a new context with a user agent and viewport
        context = await browser.new_context(
            viewport={'width': 1366, 'height': 768},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            java_script_enabled=True,
            ignore_https_errors=True,
            bypass_csp=True,
            locale='en-AU',
            timezone_id='Australia/Sydney'
        )

        # Create a single page for login and reuse it for screenshots
        page = await context.new_page()

        # Set extra HTTP headers using the correct method
        await page.set_extra_http_headers(headers={
            'Accept-Language': 'en-AU,en-US;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"macOS"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1'
        })

        # Step 1: Capture public URLs before login
        print("=== CAPTURING PUBLIC PAGES (BEFORE LOGIN) ===")
        results = []

        # Define specific names for each screenshot
        screenshot_names = {
            PUBLIC_URLS[0]: "home-page",  # https://www.kmart.com.au/
            AUTHENTICATED_URLS[0]: "shopping-bag",  # https://www.kmart.com.au/checkout/bag
            AUTHENTICATED_URLS[1]: "wishlist",  # https://www.kmart.com.au/wishlist/
            AUTHENTICATED_URLS[2]: "home-living-category",  # https://www.kmart.com.au/category/home-and-living/shop-all-home-and-living/
            AUTHENTICATED_URLS[3]: "ceramic-candle-product",  # https://www.kmart.com.au/product/red-stripe-ceramic-candle-43543175/
            AUTHENTICATED_URLS[4]: "clearance-category",  # https://www.kmart.com.au/category/clearance/shop-all-clearance/
        }

        for i, url in enumerate(PUBLIC_URLS):
            print(f"Capturing public page: {url}")
            custom_name = screenshot_names.get(url)

            # Add longer delays between requests with randomization
            if i > 0:
                delay = 3 + (i * 2) + (hash(url) % 3)  # 3-8 seconds, varies by URL
                print(f"Waiting {delay} seconds before next request...")
                await asyncio.sleep(delay)

            try:
                result = await take_screenshot(page, url, custom_name)
                if result:
                    results.append(result)
            except Exception as e:
                print(f"Error processing {url}: {str(e)}")
                results.append({
                    'url': url,
                    'filename': '',
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'success': False,
                    'error': str(e)
                })

        # Step 2: Capture search screenshot from home page
        print("\n=== CAPTURING SEARCH SCREENSHOT ===")
        try:
            await page.goto(PUBLIC_URLS[0], timeout=60000)  # Go to home page
            await page.wait_for_load_state('networkidle', timeout=30000)
            search_result = await capture_search_screenshot(page)
            if search_result:
                # Override the filename to use specific name
                search_result['filename'] = 'home-search.jpg'
                results.append(search_result)
        except Exception as e:
            print(f"Error capturing search screenshot: {str(e)}")

        # Step 3: Login if enabled and credentials are available
        login_success = True
        if LOGIN_CONFIG['enabled'] and LOGIN_CONFIG['username'] and LOGIN_CONFIG['password']:
            print("\n=== ATTEMPTING LOGIN ===")
            login_success = await login_to_site(page, LOGIN_CONFIG)
            if not login_success:
                print("Login failed, continuing with authenticated pages (will show login screens)...")
            else:
                print("Login successful, proceeding with authenticated pages...")

        # Step 4: Capture authenticated URLs after login
        if login_success or not (LOGIN_CONFIG['enabled'] and LOGIN_CONFIG['username'] and LOGIN_CONFIG['password']):
            print("\n=== CAPTURING AUTHENTICATED PAGES (AFTER LOGIN) ===")
            for i, url in enumerate(AUTHENTICATED_URLS):
                print(f"Capturing authenticated page: {url}")
                custom_name = screenshot_names.get(url)

                # Add longer delays between requests
                await asyncio.sleep(3 + (i * 2))

                try:
                    result = await take_screenshot(page, url, custom_name)
                    if result:
                        results.append(result)
                except Exception as e:
                    print(f"Error processing {url}: {str(e)}")
                    results.append({
                        'url': url,
                        'filename': '',
                        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'success': False,
                        'error': str(e)
                    })

        # Close browser
        await browser.close()

        # Generate HTML
        generate_html(results, screenshot_db=screenshot_db)

        print(f"\nScreenshots captured and saved to {OUTPUT_DIR}/")
        print("Open 'screenshots.html' in your browser to view the results.")

def generate_html(screenshots, screenshot_db=None, before_date=None, after_date=None):
    """Generate HTML with comparison layout for screenshots"""

    # Get available dates for date pickers
    available_dates = screenshot_db.get_available_dates() if screenshot_db else []
    min_date, max_date = screenshot_db.get_date_range() if screenshot_db else (None, None)

    # Default to today if no dates specified
    if after_date is None:
        after_date = datetime.now().strftime('%Y-%m-%d')

    if before_date is None:
        # Get yesterday if available, otherwise use today
        yesterday = (datetime.now().date() - timedelta(days=1)).strftime('%Y-%m-%d')
        before_date = yesterday if yesterday in available_dates else after_date

    # Ensure after_date is always the current date
    after_date = datetime.now().strftime('%Y-%m-%d')

    # Fetch screenshots for both dates
    before_screenshots = screenshot_db.get_all_screenshots_for_date(before_date) if screenshot_db else []
    after_screenshots = screenshot_db.get_all_screenshots_for_date(after_date) if screenshot_db else []

    # Create lookup dictionaries for easy access
    before_lookup = {s['page_name']: s for s in before_screenshots}
    after_lookup = {s['page_name']: s for s in after_screenshots}

    # Get all unique page names
    all_pages = set(before_lookup.keys()) | set(after_lookup.keys())
    all_pages = sorted(all_pages)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kmart Website Screenshots - Comparison</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            max-width: 1600px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        h1 {{
            color: #e31837;
            text-align: center;
            margin-bottom: 30px;
        }}
        .comparison-container {{
            display: flex;
            gap: 20px;
            margin-bottom: 20px;
        }}
        .date-column {{
            flex: 1;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .date-header {{
            background: #e31837;
            color: white;
            padding: 15px;
            text-align: center;
            font-weight: bold;
            font-size: 18px;
        }}
        .date-selector {{
            padding: 15px;
            background: #f8f9fa;
            border-bottom: 1px solid #dee2e6;
        }}
        .date-selector label {{
            display: block;
            margin-bottom: 8px;
            font-weight: bold;
        }}
        .date-selector select {{
            width: 100%;
            padding: 8px;
            border: 1px solid #ced4da;
            border-radius: 4px;
            font-size: 14px;
        }}
        .screenshot-item {{
            margin: 15px;
            border: 1px solid #dee2e6;
            border-radius: 8px;
            overflow: hidden;
            background: white;
        }}
        .screenshot-header {{
            padding: 12px;
            background: #f8f9fa;
            border-bottom: 1px solid #dee2e6;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .page-name {{
            font-weight: bold;
            color: #495057;
        }}
        .status-badge {{
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: bold;
        }}
        .status-success {{
            background: #d4edda;
            color: #155724;
        }}
        .status-error {{
            background: #f8d7da;
            color: #721c24;
        }}
        .screenshot-image {{
            width: 100%;
            height: auto;
            display: block;
            border-top: 1px solid #dee2e6;
        }}
        .no-screenshot {{
            padding: 40px 20px;
            text-align: center;
            color: #6c757d;
            background: #f8f9fa;
            border: 2px dashed #dee2e6;
            margin: 15px;
            border-radius: 8px;
        }}
        .comparison-info {{
            text-align: center;
            margin: 20px 0;
            padding: 15px;
            background: #e9ecef;
            border-radius: 8px;
            color: #495057;
        }}
        .loading {{
            text-align: center;
            padding: 40px;
            color: #6c757d;
            font-style: italic;
        }}
        @media (max-width: 768px) {{
            .comparison-container {{
                flex-direction: column;
            }}
        }}
    </style>
</head>
<body>
    <h1>Kmart Website Screenshots - Visual Comparison</h1>

    <div class="comparison-info">
        <strong>Comparison Mode:</strong> Showing visual differences between website screenshots over time
        <br>
        <strong>Available Dates:</strong> {len(available_dates)} dates with screenshots
        {f'<br><strong>Date Range:</strong> {min_date} to {max_date}' if min_date and max_date else ''}
    </div>

    <div class="comparison-container">
        <!-- Before Date Column -->
        <div class="date-column">
            <div class="date-header">Before ({before_date})</div>
            <div class="date-selector">
                <label for="beforeDateSelect">Select Date:</label>
                <select id="beforeDateSelect" onchange="updateComparison()">
                    {"".join(f'<option value="{date}" {"selected" if date == before_date else ""}>{date}</option>' for date in available_dates)}
                </select>
            </div>"""

    # Generate screenshot items for before date
    for page_name in all_pages:
        before_shot = before_lookup.get(page_name)

        html_content += f'''
            <div class="screenshot-item">
                <div class="screenshot-header">
                    <span class="page-name">{page_name.replace('-', ' ').title()}</span>
                    <span class="status-badge {'status-success' if before_shot else 'status-error'}">
                        {'✓ Available' if before_shot else '✗ Missing'}
                    </span>
                </div>'''

        if before_shot:
            image_data_url = get_image_data_url(before_shot['image_data'], before_shot['filename'])
            html_content += f'''
                <img src="{image_data_url}"
                     alt="Screenshot of {before_shot['url']} on {before_date}"
                     class="screenshot-image"
                     loading="lazy">'''
        else:
            html_content += '''
                <div class="no-screenshot">
                    No screenshot available for this page on the selected date
                </div>'''

        html_content += '''
            </div>'''

    html_content += '''
        </div>

        <!-- After Date Column -->
        <div class="date-column">
            <div class="date-header">After ({after_date})</div>
            <div class="date-selector">
                <label for="afterDateSelect">Select Date:</label>
                <select id="afterDateSelect" onchange="updateComparison()">
                    {"".join(f'<option value="{date}" {"selected" if date == after_date else ""}>{date}</option>' for date in available_dates)}
                </select>
            </div>'''

    # Generate screenshot items for after date
    for page_name in all_pages:
        after_shot = after_lookup.get(page_name)

        html_content += f'''
            <div class="screenshot-item">
                <div class="screenshot-header">
                    <span class="page-name">{page_name.replace('-', ' ').title()}</span>
                    <span class="status-badge {'status-success' if after_shot else 'status-error'}">
                        {'✓ Available' if after_shot else '✗ Missing'}
                    </span>
                </div>'''

        if after_shot:
            image_data_url = get_image_data_url(after_shot['image_data'], after_shot['filename'])
            html_content += f'''
                <img src="{image_data_url}"
                     alt="Screenshot of {after_shot['url']} on {after_date}"
                     class="screenshot-image"
                     loading="lazy">'''
        else:
            html_content += '''
                <div class="no-screenshot">
                    No screenshot available for this page on the selected date
                </div>'''

        html_content += '''
            </div>'''

    html_content += '''
        </div>
    </div>

    <script>
        function updateComparison() {
            const beforeDate = document.getElementById('beforeDateSelect').value;
            const afterDate = document.getElementById('afterDateSelect').value;

            // Update URL parameters to reflect date selection
            const url = new URL(window.location);
            url.searchParams.set('before', beforeDate);
            url.searchParams.set('after', afterDate);
            window.location.href = url.toString();
        }

        // Auto-reload if URL parameters change (for bookmarking)
        window.addEventListener('load', function() {
            const urlParams = new URLSearchParams(window.location.search);
            const beforeParam = urlParams.get('before');
            const afterParam = urlParams.get('after');

            if (beforeParam) {
                document.getElementById('beforeDateSelect').value = beforeParam;
            }
            if (afterParam) {
                document.getElementById('afterDateSelect').value = afterParam;
            }
        });
    </script>
</body>
</html>'''

    with open(os.path.join(OUTPUT_DIR, 'screenshots.html'), 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"✅ Generated comparison HTML with {len(all_pages)} pages")
    print(f"   Before date: {before_date} ({len(before_screenshots)} screenshots)")
    print(f"   After date: {after_date} ({len(after_screenshots)} screenshots)")

if __name__ == "__main__":
    asyncio.run(main())
