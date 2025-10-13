#!/usr/bin/env python3
"""
Sample script: BrowserStack App Automate (iOS) + Appium + Percy

This script shows how to:
 - Connect to BrowserStack App Automate using Appium and a BrowserStack app URL (bs://<app-id>)
 - Launch the iOS app on a real device hosted by BrowserStack
 - Capture a full-screen screenshot
 - Send the screenshot to Percy (if a Percy SDK/agent is available)

Notes
 - Playwright cannot automate native mobile apps. Appium is required for native iOS apps
 - To upload snapshots to Percy easily, run the script under the Percy agent:
     export PERCY_TOKEN=your_percy_token
     percy exec -- python browserstack_appium_percy_ios.py --app bs://<app-id>
 - You can also provide BrowserStack credentials via env vars: BROWSERSTACK_USER and BROWSERSTACK_KEY

Requirements
 - pip install Appium-Python-Client requests
 - Optional: pip install percy (or the Percy SDK you prefer for your project)
"""

import argparse
import base64
import os
import tempfile
import time
import traceback

import json
import requests
from appium import webdriver
from appium.webdriver.common.appiumby import AppiumBy
from appium.webdriver.common.touch_action import TouchAction
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException


def create_driver(app_bs_url, bs_user, bs_key, device_name, os_version, test_name):
    """Create an Appium driver connected to BrowserStack App Automate (iOS).

    app_bs_url: BrowserStack app url, e.g. bs://<app-id>
    bs_user / bs_key: BrowserStack credentials
    device_name: e.g. 'iPhone 14'
    os_version: e.g. '16.0'
    """
    capabilities = {
        'platformName': 'iOS',
        'deviceName': device_name,
        'platformVersion': os_version,
        'app': app_bs_url,
        'automationName': 'XCUITest',
        # BrowserStack specific capabilities
        'browserstack.user': bs_user,
        'browserstack.key': bs_key,
        'project': 'Example - Appium + Percy',
        'build': 'Appium-Python Percy Build',
        'name': test_name,
        'browserstack.debug': True,
        'autoAcceptAlerts': True,
    }

    hub_url = 'https://hub-cloud.browserstack.com/wd/hub'
    driver = webdriver.Remote(command_executor=hub_url, desired_capabilities=capabilities)
    return driver


def save_screenshot_to_temp(png_bytes, prefix='bs_app_screenshot'):
    fd, path = tempfile.mkstemp(prefix=prefix, suffix='.png')
    os.close(fd)
    with open(path, 'wb') as f:
        f.write(png_bytes)
    return path


def _map_by(by_str: str):
    """Map a short string to an AppiumBy constant.

    Supported: accessibility_id, id, xpath, class_name, ios_predicate
    """
    lookup = {
        'accessibility_id': AppiumBy.ACCESSIBILITY_ID,
        'id': AppiumBy.ID,
        'xpath': AppiumBy.XPATH,
        'class_name': AppiumBy.CLASS_NAME,
        'ios_predicate': AppiumBy.IOS_PREDICATE,
    }
    return lookup.get(by_str, AppiumBy.ACCESSIBILITY_ID)


def find(driver, by, value, timeout=30, clickable=False):
    """Wait for an element and return it, or None on timeout.

    by: AppiumBy.* constant
    value: locator string
    clickable: if True, wait until element is clickable
    """
    wait = WebDriverWait(driver, timeout)
    try:
        if clickable:
            return wait.until(EC.element_to_be_clickable((by, value)))
        return wait.until(EC.presence_of_element_located((by, value)))
    except TimeoutException:
        return None


def tap(driver, by, value, timeout=30):
    el = find(driver, by, value, timeout=timeout, clickable=True)
    if not el:
        raise NoSuchElementException(f'Element not found (tap): {by}={value}')
    el.click()
    return el


def input_text(driver, by, value, text, timeout=30, clear=True):
    el = find(driver, by, value, timeout=timeout, clickable=False)
    if not el:
        raise NoSuchElementException(f'Element not found (input): {by}={value}')
    try:
        if clear:
            el.clear()
    except Exception:
        # Some elements may not support clear(); ignore
        pass
    el.send_keys(text)
    return el


def swipe_up(driver, duration=800):
    """Perform a swipe up gesture (useful for scrolling)."""
    size = driver.get_window_size()
    start_x = int(size['width'] * 0.5)
    start_y = int(size['height'] * 0.8)
    end_x = start_x
    end_y = int(size['height'] * 0.2)
    TouchAction(driver).press(x=start_x, y=start_y).wait(ms=duration).move_to(x=end_x, y=end_y).release().perform()


def scroll_to_element(driver, by, value, max_swipes=5):
    """Try to find an element by scrolling the screen up until found or attempts exhausted."""
    for i in range(max_swipes + 1):
        el = find(driver, by, value, timeout=1, clickable=False)
        if el is not None:
            return el
        swipe_up(driver)
        time.sleep(0.8)
    return None


def take_snapshot(driver, name, save_local=True, use_percy=True):
    """Capture a screenshot, optionally save locally and attempt to send to Percy.

    Returns tuple (local_path_or_None, percy_result_bool)
    """
    png = driver.get_screenshot_as_png()
    local_path = None
    if save_local:
        safe_name = name.replace(' ', '_')
        local_path = save_screenshot_to_temp(png, prefix=safe_name)
        print('Saved snapshot to:', local_path)

    percy_ok = False
    if use_percy:
        print('Attempting Percy SDK snapshot...')
        percy_ok = try_percy_snapshot_with_sdk(driver, name=name)
        if not percy_ok and os.environ.get('PERCY_TOKEN'):
            print('Falling back to Percy Agent POST...')
            percy_ok = try_percy_snapshot_via_agent(png, name=name, widths=[])

    return local_path, percy_ok


def run_actions(driver, actions, snapshot_each_step=False):
    """Run a list of actions (dicts). Example action items:

    {"action":"tap", "by":"accessibility_id", "value":"login_button", "name":"tap-login"}
    {"action":"input", "by":"accessibility_id", "value":"username", "text":"me@example.com"}
    {"action":"wait", "timeout":3}
    {"action":"snapshot", "name":"home screen"}
    """
    for idx, a in enumerate(actions):
        action = a.get('action')
        print(f'Executing action #{idx}: {action} -> {a.get("name") or a.get("value") or ""}')
        if action == 'tap':
            by = _map_by(a.get('by', 'accessibility_id'))
            tap(driver, by, a['value'], timeout=a.get('timeout', 30))
        elif action == 'input':
            by = _map_by(a.get('by', 'accessibility_id'))
            input_text(driver, by, a['value'], a.get('text', ''), timeout=a.get('timeout', 30))
        elif action == 'wait':
            time.sleep(a.get('timeout', 1))
        elif action == 'snapshot':
            take_snapshot(driver, a.get('name', f'step_{idx}'))
        elif action == 'scroll_to':
            by = _map_by(a.get('by', 'accessibility_id'))
            el = scroll_to_element(driver, by, a['value'], max_swipes=a.get('max_swipes', 5))
            if not el:
                raise NoSuchElementException(f"Could not find element to scroll to: {a.get('value')}")
        else:
            print('Unknown action:', action)

        # Optionally take a snapshot after each step
        if snapshot_each_step and action != 'snapshot':
            snap_name = a.get('name') or a.get('value') or f'step_{idx}'
            try:
                take_snapshot(driver, f'step_{idx} - {snap_name}')
            except Exception:
                print('Snapshot after step failed; continuing')


def sample_login_flow(driver, username, password, snapshot_prefix='login_flow', wait_after_login=6):
    """A small example flow that demonstrates tapping, typing and snapshots.

    Replace the accessibility ids below with values from your app.
    """
    # Replace these IDs with the ones used in your app
    LOGIN_BTN = 'login_button'
    USERNAME_FIELD = 'username_field'
    PASSWORD_FIELD = 'password_field'
    SUBMIT_BTN = 'submit_button'
    HOME_SCREEN_MARKER = 'home_screen_marker'

    print('Tapping login button...')
    tap(driver, AppiumBy.ACCESSIBILITY_ID, LOGIN_BTN)

    print('Entering username...')
    input_text(driver, AppiumBy.ACCESSIBILITY_ID, USERNAME_FIELD, username or 'example@example.com')

    print('Entering password...')
    input_text(driver, AppiumBy.ACCESSIBILITY_ID, PASSWORD_FIELD, password or 'supersecret')

    print('Submitting...')
    tap(driver, AppiumBy.ACCESSIBILITY_ID, SUBMIT_BTN)

    print(f'Waiting {wait_after_login}s for login to complete...')
    time.sleep(wait_after_login)

    print('Taking post-login snapshot...')
    take_snapshot(driver, f'{snapshot_prefix} - home')

    # Example: navigate to profile via accessibility id or xpath and snapshot
    try:
        PROFILE_BTN = 'profile_button'
        print('Navigating to profile...')
        tap(driver, AppiumBy.ACCESSIBILITY_ID, PROFILE_BTN, timeout=10)
        time.sleep(2)
        take_snapshot(driver, f'{snapshot_prefix} - profile')
    except Exception:
        print('Profile navigation failed or element not present; skipping profile snapshot')


def try_percy_snapshot_with_sdk(driver, name='App Snapshot'):
    """Try to call a Percy Python SDK that supports Selenium/Appium drivers.
    This is a best-effort convenience: depending on which Percy SDK you installed
    the API may differ. We try a couple of common entry points.
    """
    try:
        # Some Percy Python SDKs provide a helper like `percy.snapshot(driver, name=...)` or
        # `percy_snapshot(driver, 'name')`. Try common variants.
        import percy

        # 1) percy.snapshot(driver, name)
        if hasattr(percy, 'snapshot'):
            percy.snapshot(driver, name=name)
            return True

        # 2) percy.percy_snapshot(driver, name)
        if hasattr(percy, 'percy_snapshot'):
            percy.percy_snapshot(driver, name)
            return True

        # 3) percy.Percy(driver).snapshot(name)
        if hasattr(percy, 'Percy'):
            percy.Percy(driver).snapshot(name)
            return True

        print('Percy module imported but no known snapshot API found.')
        return False
    except Exception:
        traceback.print_exc()
        return False


def try_percy_snapshot_via_agent(png_bytes, name='App Snapshot', widths=None, min_height=None):
    """Send a minimal snapshot payload to a running Percy Agent (percy exec).

    Percy Agent commonly listens on http://localhost:5338. The exact HTTP
    contract is internal to the Percy SDK, so this function performs a minimal
    best-effort POST to the `/percy/snapshot` endpoint with a base64 PNG.

    This may need adjustments depending on the Percy Agent version / SDK
    you are using.
    """
    agent_base = os.environ.get('PERCY_AGENT_URL', 'http://localhost:5338')
    endpoint = agent_base.rstrip('/') + '/percy/snapshot'
    payload = {
        'name': name,
        # A URL is required by Percy; we provide an app-like URL so UI shows meaningful text
        'url': 'app://' + (os.environ.get('PERCY_APP_ID', 'browserstack-app')),
        # widths and minimumHeight are optional; Percy typically expects an array of widths
        'widths': widths or [],
    }

    # Some Percy agents accept the screenshot as top-level base64 string; others
    # expect resources. We include a best-effort 'screenshot' field.
    try:
        payload['screenshot'] = base64.b64encode(png_bytes).decode('ascii')
        headers = {'Content-Type': 'application/json'}
        resp = requests.post(endpoint, json=payload, headers=headers, timeout=20)
        resp.raise_for_status()
        print('Percy agent responded:', resp.status_code)
        return True
    except Exception:
        print('Failed to send snapshot to Percy agent:')
        traceback.print_exc()
        return False


def set_browserstack_status(driver, status: str, reason: str = ''):
    """Mark the BrowserStack session status using the browserstack_executor Appium hook.

    status: 'passed' or 'failed'
    reason: optional message
    """
    try:
        payload = {
            'action': 'setSessionStatus',
            'arguments': {
                'status': status,
                'reason': reason,
            }
        }
        # BrowserStack expects a special execute_script call with the payload JSON
        driver.execute_script('browserstack_executor: ' + json.dumps(payload))
        print(f'BrowserStack session marked as {status} ({reason})')
    except Exception:
        print('Failed to set BrowserStack session status:')
        traceback.print_exc()


def main():
    parser = argparse.ArgumentParser(description='BrowserStack App Automate (iOS) + Percy example')
    parser.add_argument('--app', required=True, help='BrowserStack app URL, e.g. bs://<app-id>')
    parser.add_argument('--device', default='iPhone 14', help='Device name (default: iPhone 14)')
    parser.add_argument('--os-version', dest='os_version', default='16.0', help='iOS version (default: 16.0)')
    parser.add_argument('--wait', type=int, default=6, help='Seconds to wait after app launch before screenshot')
    parser.add_argument('--name', default='BS iOS App Snapshot', help='Snapshot name sent to Percy')
    parser.add_argument('--login', action='store_true', help='Run the sample login flow (example)')
    parser.add_argument('--username', default=None, help='Username for the sample login flow')
    parser.add_argument('--password', default=None, help='Password for the sample login flow')
    parser.add_argument('--steps', default=None, help='Path to a JSON steps file or an inline JSON string describing actions')
    parser.add_argument('--snapshot-each-step', action='store_true', help='Take a snapshot after each action in --steps')
    parser.add_argument('--mark-session', action='store_true', help='Mark BrowserStack session status as passed/failed automatically')
    args = parser.parse_args()

    bs_user = os.environ.get('BROWSERSTACK_USER') or os.environ.get('BROWSERSTACK_USERNAME')
    bs_key = os.environ.get('BROWSERSTACK_KEY') or os.environ.get('BROWSERSTACK_ACCESS_KEY')
    if not bs_user or not bs_key:
        print('Please set BROWSERSTACK_USER and BROWSERSTACK_KEY environment variables.')
        return

    print('Starting Appium session on BrowserStack...')
    driver = create_driver(args.app, bs_user, bs_key, args.device, args.os_version, args.name)
    status = 'passed'
    reason = 'All actions completed'
    try:
        # Give the app some time to settle after install / launch
        print(f'Waiting {args.wait}s for the app to become ready...')
        time.sleep(args.wait)

        if args.steps:
            # Load actions
            actions = None
            try:
                if os.path.exists(args.steps):
                    with open(args.steps, 'r', encoding='utf-8') as fh:
                        actions = json.load(fh)
                else:
                    actions = json.loads(args.steps)
            except Exception as e:
                print('Failed to parse --steps JSON:', e)
                raise

            print(f'Running {len(actions)} actions from steps...')
            run_actions(driver, actions, snapshot_each_step=args.snapshot_each_step)

        elif args.login:
            print('Running sample login flow...')
            sample_login_flow(driver, args.username, args.password, snapshot_prefix=args.name, wait_after_login=args.wait)

        else:
            # Default behavior: take a single screenshot and try to send to Percy
            print('Capturing full-screen screenshot...')
            png = driver.get_screenshot_as_png()
            path = save_screenshot_to_temp(png)
            print('Screenshot saved to:', path)

            # Try Percy SDK integration first
            print('Attempting Percy SDK snapshot (if installed)...')
            sdk_ok = try_percy_snapshot_with_sdk(driver, name=args.name)
            if sdk_ok:
                print('Percy SDK snapshot sent (best-effort).')
            elif os.environ.get('PERCY_TOKEN'):
                print('PERCY_TOKEN is set; attempting to POST to Percy Agent endpoint...')
                agent_ok = try_percy_snapshot_via_agent(png, name=args.name, widths=[], min_height=None)
                if agent_ok:
                    print('Percy Agent accepted the snapshot (best-effort).')
                else:
                    print('Percy Agent upload failed.')
            else:
                print('Percy upload was not performed. If you want Percy integration:')
                print(' - Install a Percy SDK that supports Appium/Selenium (Python) or run under `percy exec`')
                print(' - Example: export PERCY_TOKEN=...; percy exec -- python browserstack_appium_percy_ios.py --app bs://<app-id>')

    except Exception as e:
        status = 'failed'
        reason = f'Exception during run: {e}'
        print('Error during execution:')
        traceback.print_exc()
        # Re-raise after marking status in finally-block if needed
        raise
    finally:
        # Optionally mark BrowserStack session status (passed/failed)
        if args.mark_session:
            try:
                set_browserstack_status(driver, status, reason)
            except Exception:
                print('Failed to mark BrowserStack session status; continuing to quit driver')

        try:
            driver.quit()
        except Exception:
            pass


if __name__ == '__main__':
    main()
