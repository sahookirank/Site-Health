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
from datetime import datetime
from playwright.async_api import async_playwright
from pathlib import Path
OUTPUT_DIR = "screenshots"
# Public URLs to capture before login
PUBLIC_URLS = [
    "https://www.kmart.com.au/",
    "https://www.kmart.com.au/category/home-and-living/shop-all-home-and-living/",
    "https://www.kmart.com.au/product/red-stripe-ceramic-candle-43543175/",
    "https://www.kmart.com.au/category/clearance/shop-all-clearance/"
]

# Authenticated URLs to capture after login
AUTHENTICATED_URLS = [
    "https://www.kmart.com.au/checkout/bag",
    "https://www.kmart.com.au/wishlist/"
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
    if custom_name:
        filename = custom_name
    else:
        filename = url.replace('https://', '').replace('/', '_').replace('?', '_')
        if len(filename) > 50:  # Limit filename length
            filename = filename[:50]

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
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
            java_script_enabled=True,
            ignore_https_errors=True,
            bypass_csp=True
        )

        # Create a single page for login and reuse it for screenshots
        page = await context.new_page()

        # Set extra HTTP headers using the correct method
        await page.set_extra_http_headers(headers={
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Referer': 'https://www.google.com/'
        })

        # Step 1: Capture public URLs before login
        print("=== CAPTURING PUBLIC PAGES (BEFORE LOGIN) ===")
        results = []

        # Define specific names for each screenshot
        screenshot_names = {
            PUBLIC_URLS[0]: "home-page",  # https://www.kmart.com.au/
            PUBLIC_URLS[1]: "home-living-category",  # https://www.kmart.com.au/category/home-and-living/shop-all-home-and-living/
            PUBLIC_URLS[2]: "ceramic-candle-product",  # https://www.kmart.com.au/product/red-stripe-ceramic-candle-43543175/
            PUBLIC_URLS[3]: "clearance-category",  # https://www.kmart.com.au/category/clearance/shop-all-clearance/
            AUTHENTICATED_URLS[0]: "shopping-bag",  # https://www.kmart.com.au/checkout/bag
            AUTHENTICATED_URLS[1]: "wishlist"  # https://www.kmart.com.au/wishlist/
        }

        for i, url in enumerate(PUBLIC_URLS):
            print(f"Capturing public page: {url}")
            custom_name = screenshot_names.get(url)

            # Add a small delay between requests
            if i > 0:
                await asyncio.sleep(2)

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

                # Add a small delay between requests
                await asyncio.sleep(2)

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
        generate_html(results)

        print(f"\nScreenshots captured and saved to {OUTPUT_DIR}/")
        print("Open 'screenshots.html' in your browser to view the results.")

def generate_html(screenshots):
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kmart Website Screenshots</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        h1 {
            color: #e31837;
            text-align: center;
            margin-bottom: 30px;
        }
        .screenshot-container {
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 20px;
            overflow: hidden;
        }
        .screenshot-info {
            padding: 15px;
            border-bottom: 1px solid #eee;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .screenshot-info a {
            color: #0066cc;
            text-decoration: none;
            word-break: break-all;
            flex-grow: 1;
        }
        .screenshot-info a:hover {
            text-decoration: underline;
        }
        .screenshot-content {
            display: none;
            padding: 10px;
            background: #f9f9f9;
        }
        .screenshot-content.expanded {
            display: block;
            animation: fadeIn 0.3s ease-in-out;
        }
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        .screenshot {
            max-width: 100%;
            height: auto;
            border: 1px solid #eee;
            box-sizing: border-box;
            display: block;
            margin: 10px 0;
        }
        .screenshot-error {
            padding: 20px;
            color: #d32f2f;
            text-align: center;
            background-color: #ffebee;
            border: 1px dashed #ef9a9a;
            margin: 10px 0;
            border-radius: 4px;
        }
        .timestamp {
            color: #666;
            font-size: 0.9em;
            margin: 10px 0;
        }
        .no-screenshots {
            text-align: center;
            color: #666;
            padding: 40px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .toggle-button {
            background: #e31837;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 5px 10px;
            margin-left: 15px;
            cursor: pointer;
            font-size: 0.9em;
            flex-shrink: 0;
        }
        .toggle-button:hover {
            background: #c4142b;
        }
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }
        .status-success {
            background-color: #4caf50;
        }
        .status-error {
            background-color: #f44336;
        }
        .loading {
            text-align: center;
            padding: 20px;
            color: #666;
            font-style: italic;
        }
    </style>
</head>
<body>
    <h1>Kmart Website Screenshots</h1>
    <div class="screenshots">
"""

    if not screenshots:
        html_content += """
        <div class="no-screenshots">
            <p>No screenshots were captured. Please check the console for errors.</p>
        </div>
        """
    else:
        for item in screenshots:
            file_path = os.path.join(OUTPUT_DIR, item['filename'])
            file_exists = os.path.exists(file_path) and os.path.getsize(file_path) > 0
            
            html_content += f"""
            <div class="screenshot-container">
                <div class="screenshot-info">
                    <span class="status-indicator {'status-success' if file_exists else 'status-error'}"></span>
                    <a href="{item['url']}" target="_blank" onclick="event.stopPropagation();">{item['url']}</a>
                    <button class="toggle-button" onclick="toggleScreenshot(this)">Show Screenshot</button>
                </div>
                <div class="screenshot-content">
                    <div class="timestamp">Captured on: {item['timestamp']}</div>
            """
            
            if file_exists:
                html_content += f'<div class="screenshot-wrapper"><img src="{item["filename"]}" alt="Screenshot of {item["url"]}" class="screenshot" onerror="this.onerror=null;this.parentElement.innerHTML+=\'<div class=\\\'screenshot-error\\\'>Failed to load screenshot</div>\';"></div>'
            else:
                html_content += '<div class="screenshot-error">Screenshot not available or failed to load</div>'
            
            html_content += """
                </div>
            </div>
            """

    html_content += """
    </div>
    <script>
        function toggleScreenshot(button) {
            const container = button.closest('.screenshot-container');
            const content = container.querySelector('.screenshot-content');
            const isExpanded = content.classList.contains('expanded');
            
            // Close all other open items
            document.querySelectorAll('.screenshot-content.expanded').forEach(item => {
                if (item !== content) {
                    item.classList.remove('expanded');
                    const otherBtn = item.closest('.screenshot-container').querySelector('.toggle-button');
                    if (otherBtn) otherBtn.textContent = 'Show Screenshot';
                }
            });
            
            // Toggle current item
            content.classList.toggle('expanded');
            button.textContent = isExpanded ? 'Show Screenshot' : 'Hide Screenshot';
        }
    </script>
</body>
</html>
    """
    
    with open(os.path.join(OUTPUT_DIR, 'screenshots.html'), 'w', encoding='utf-8') as f:
        f.write(html_content)

if __name__ == "__main__":
    asyncio.run(main())
