import requests
from bs4 import BeautifulSoup
import logging
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed, wait
import queue
import time
import threading
from datetime import datetime
import pandas as pd
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Union
import argparse

STOP_EVENT = threading.Event()

logged_milestones = set()

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.FileHandler('link_check_log.txt'),
                        logging.StreamHandler()
                    ])
logging.getLogger("urllib3").setLevel(logging.ERROR)

MAX_CONNECTIONS = 100
REQUEST_TIMEOUT = 3
MAX_RETRIES = 2
RATE_LIMIT = 0.1
MAX_PATH_LENGTH = 255  # Max characters for the Path string in CSV
# MAX_URLS_TO_CHECK = 5000 # Limit removed for full crawl
START_URL = 'https://www.kmart.com.au/'

results_queue = queue.Queue()

session = requests.Session()
# Custom User-Agent to reduce chances of being blocked by Akamai. Include 'kmart' as requested.
# You can customize this string if needed, or set the KMART_USER_AGENT environment variable to override.
KMART_USER_AGENT = 'kmart-linkchecker/1.0 (+https://www.kmart.com.au/)'
session.headers.update({'User-Agent': KMART_USER_AGENT})
retry_strategy = Retry(total=MAX_RETRIES, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=MAX_CONNECTIONS, pool_maxsize=MAX_CONNECTIONS)
session.mount("http://", adapter)
session.mount("https://", adapter)

checked_links = set()
checked_links_lock = threading.Lock()
url_paths = {}

VALID_STATUS_CODES = {200, 201, 202, 203, 204}
REDIRECT_STATUS_CODES = {301, 302, 303, 307, 308}
MAX_REDIRECTS = 5

def check_link(url, retries=MAX_RETRIES):
    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        return response.status_code
    except requests.RequestException as e:
        logging.error(f"Error checking {url}: {e}")
        return None
    finally:
        time.sleep(RATE_LIMIT)

def get_links(url):
    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT)
        if response.status_code != 200:
            logging.warning(f"Non-200 status code {response.status_code} for URL: {url}")
            return []

        soup = BeautifulSoup(response.text, 'html.parser')
        links = set()
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            full_url = urljoin(url, href)
            if "kmart.com.au" in full_url and not any(x in full_url for x in ["jobs.", "careers", "wcsstore", "inactive"]):
                links.add(full_url)
        return links
    except Exception as e:
        logging.error(f"Error fetching links from {url}: {e}")
        return []

def verify_link_in_ui(path, target_url):
    pages = [s.strip() for s in path.split("->")]
    if len(pages) < 2:
        return "N/A"
    parent_url = pages[-2]
    try:
        response = session.get(parent_url, timeout=REQUEST_TIMEOUT)
        return "Yes" if target_url in response.text else "No"
    except Exception:
        return "No"

def worker(url, path):
    if STOP_EVENT.is_set():
        return [], path
    with checked_links_lock:
        if url in checked_links: # MAX_URLS_TO_CHECK limit removed
            return [], path
        checked_links.add(url)

    url_paths[url] = path
    logging.info(f"Checking link: {url}")
    status = check_link(url)
    visible = verify_link_in_ui(path, url)

    check_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    results_queue.put({
        'Timestamp': check_time,
        'URL': url,
        'Status': status,
        'Path': path,
        'Visible': visible
    })

    if status == 200 and not STOP_EVENT.is_set():
        return get_links(url), path
    return [], path

def main(start_url=None, max_urls: int | None = None):
    if start_url is None:
        start_url = START_URL
    start_time = time.time()
    futures_to_urls = {}

    with ThreadPoolExecutor(max_workers=20) as executor:
        future = executor.submit(worker, start_url, start_url)
        futures_to_urls[future] = start_url

        while futures_to_urls:
            done, _ = wait(futures_to_urls, timeout=1, return_when='FIRST_COMPLETED')
            for future in done:
                try:
                    new_links, path = future.result()
                    for link in new_links:
                        if link not in checked_links: # MAX_URLS_TO_CHECK limit removed
                            new_path = f"{path} -> {link}"
                            new_path_full = f"{path} -> {link}"
                            if len(new_path_full) > MAX_PATH_LENGTH:
                                # Keep the end of the path, which is more relevant, and part of the beginning
                                # e.g., start_url -> ... -> end_of_path
                                # To ensure the start_url is always present if path is very long:
                                parts = new_path_full.split(' -> ')
                                if len(parts) > 2: # Ensure there's at least a start, middle, and end part
                                    # Calculate remaining length for the end part after start_url and ' -> ... -> '
                                    # len(start_url) + len(' -> ... -> ') + len(end_part) <= MAX_PATH_LENGTH
                                    # len(' -> ... -> ') is 12 characters
                                    # We also need to account for the actual link being added
                                    start_part = parts[0]
                                    end_part = parts[-1]
                                    # Available length for the end part, considering the start_part and ellipsis placeholder
                                    available_for_end = MAX_PATH_LENGTH - (len(start_part) + 12)
                                    if available_for_end < len(end_part) and available_for_end > 0:
                                        # Truncate the end_part if it's too long to fit with start_part and ellipsis
                                        # but ensure we don't cut it to zero or negative length
                                        truncated_end_part = end_part[:available_for_end]
                                        new_path = f"{start_part} -> ... -> {truncated_end_part}"
                                    elif available_for_end >= len(end_part):
                                        # The end_part fits entirely with start_part and ellipsis
                                        new_path = f"{start_part} -> ... -> {end_part}"
                                    else:
                                        # Not enough space even for a truncated end_part with the start_part, just truncate the whole thing
                                        new_path = new_path_full[:MAX_PATH_LENGTH-3] + "..."
                                else:
                                    # Path is not long enough to need complex truncation (e.g. start -> end), just simple truncation
                                    new_path = new_path_full[:MAX_PATH_LENGTH-3] + "..." if len(new_path_full) > MAX_PATH_LENGTH else new_path_full
                            else:
                                new_path = new_path_full
                            
                            if not STOP_EVENT.is_set():
                                new_future = executor.submit(worker, link, new_path)
                                futures_to_urls[new_future] = link
                except Exception as e:
                    logging.error(f"Error processing future: {e}")
                del futures_to_urls[future]

                curr_count = len(checked_links)
                if curr_count % 100 == 0 and curr_count not in logged_milestones:
                    logged_milestones.add(curr_count)
                    elapsed = time.time() - start_time
                    logging.info(f"Processed {curr_count} links in {elapsed:.2f} seconds")

            # Optional max URLs guard for testing
            if max_urls is not None and len(checked_links) >= max_urls:
                logging.info(f"Reached max URLs limit ({max_urls}), stopping crawl...")
                STOP_EVENT.set()
                # Cancel any not-yet-started futures
                for f in list(futures_to_urls.keys()):
                    f.cancel()
                break

    results = []
    while not results_queue.empty():
        results.append(results_queue.get())
    df = pd.DataFrame(results, columns=['Timestamp', 'URL', 'Status', 'Path', 'Visible'])
    df['Status'] = pd.to_numeric(df['Status'], errors='coerce')
    csv_path = 'au_link_check_results.csv'
    df.to_csv(csv_path, index=False)
    print(f"✅ AU CSV report saved to {csv_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kmart AU link checker")
    parser.add_argument("--start-url", default=START_URL, help="Starting URL for crawl")
    parser.add_argument("--max-urls", type=int, default=None, help="Optional limit of URLs to check (for testing)")
    args = parser.parse_args()

    main(start_url=args.start_url, max_urls=args.max_urls)