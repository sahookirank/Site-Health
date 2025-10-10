#!/usr/bin/env python3
"""
Generate the Page Views tab HTML for a selected day using live New Relic data.

Example:
    python preview_page_views.py --account-id 123456 --date 2025-10-08

You will be prompted for the NEWRELIC_COOKIE if it is not supplied via flag or
environment variable.
"""

import argparse
import json
import os
from datetime import datetime, timedelta
from getpass import getpass

import requests

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # Python < 3.9 fallback

from newrelic_top_products import (
    build_page_views_container_html,
    parse_response_data,
)

DEFAULT_TIMEZONE = "Australia/Melbourne"
DEFAULT_BASE_URL = "https://chartdata.service.newrelic.com/v3/nrql?"


def _default_date(timezone_name: str) -> str:
    timezone_name = timezone_name or DEFAULT_TIMEZONE
    now = None
    if ZoneInfo:
        try:
            now = datetime.now(ZoneInfo(timezone_name))
        except Exception:
            now = None
    if now is None:
        now = datetime.now()
    return now.date().isoformat()


def _format_offset(dt: datetime) -> str:
    offset = dt.utcoffset() or timedelta()
    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    total_minutes = abs(total_minutes)
    hours, minutes = divmod(total_minutes, 60)
    return f"{sign}{hours:02d}:{minutes:02d}"


def _format_dt(dt: datetime) -> str:
    return f"{dt.strftime('%Y-%m-%d %H:%M:%S')} {_format_offset(dt)}"


def _compute_window(date_str: str, timezone_name: str) -> tuple[str, str]:
    try:
        base_date = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("Date must be in YYYY-MM-DD format") from exc

    tz = None
    if ZoneInfo:
        try:
            tz = ZoneInfo(timezone_name)
        except Exception:
            tz = None

    if tz is None:
        if timezone_name != DEFAULT_TIMEZONE:
            print(f"⚠️  Falling back to UTC offset because timezone '{timezone_name}' "
                  "is unavailable on this Python version.")
        start = base_date
        end = start + timedelta(days=1)
    else:
        start = datetime(base_date.year, base_date.month, base_date.day, tzinfo=tz)
        end = start + timedelta(days=1)

    return _format_dt(start), _format_dt(end)


def _build_headers(cookie: str) -> dict:
    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Content-Type": "application/json",
        "Referer": "https://one.newrelic.com/",
        "sec-ch-ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"),
        "x-query-source-capability-id": "QUERY_BUILDER",
        "x-query-source-component": "Billboard Visualization",
        "x-query-source-component-id": "viz-billboard",
        "x-query-source-feature": "Query your data",
        "x-query-source-feature-id": "unified-data-exploration.home",
        "x-query-source-ui-package-id": "viz",
        "x-requested-with": "XMLHttpRequest",
        "newrelic-requesting-services": "viz|nr1-ui",
    }
    headers["Cookie"] = cookie
    return headers


def _extract_series(json_data):
    if not isinstance(json_data, dict):
        return json_data

    data_section = json_data.get("data", {})
    actor = data_section.get("actor", {})
    nrql_section = actor.get("nrql")
    if nrql_section:
        if isinstance(nrql_section, dict):
            for key in ("results", "facets", "raw"):
                if key in nrql_section:
                    return nrql_section[key]
        if isinstance(nrql_section, list):
            return nrql_section

    if "results" in json_data:
        return json_data["results"]

    return json_data


def _run_nrql(base_url: str, headers: dict, account_id: int, nrql: str) -> list[dict]:
    payload = {
        "account_ids": [account_id],
        "nrql": nrql,
    }
    response = requests.post(base_url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    json_data = response.json()
    return parse_response_data(_extract_series(json_data))


def _annotate_timestamp(items: list[dict], label: str) -> None:
    for item in items:
        item["timestamp"] = label


def _render_html(top_products, top_pages) -> str:
    return build_page_views_container_html(top_products, top_pages, [])


def generate_preview(args):
    account_id = args.account_id or os.getenv("NEWRELIC_ACCOUNT_ID")
    if not account_id:
        raise SystemExit("❌ NEWRELIC_ACCOUNT_ID is required (flag or environment variable).")

    try:
        account_id_int = int(account_id)
    except ValueError as exc:
        raise SystemExit("❌ Account ID must be an integer.") from exc

    cookie = args.cookie or os.getenv("NEWRELIC_COOKIE") or ""
    if not cookie:
        cookie = getpass("Enter NEWRELIC_COOKIE: ").strip()
    if not cookie:
        raise SystemExit("❌ Cookie is required for authentication.")

    timezone_name = args.timezone or DEFAULT_TIMEZONE
    query_date = args.date or _default_date(timezone_name)
    since_str, until_str = _compute_window(query_date, timezone_name)

    base_url = args.base_url or os.getenv("NEWRELIC_BASE_URL") or DEFAULT_BASE_URL
    headers = _build_headers(cookie)

    print(f"📅 Querying PageView data for {query_date} ({timezone_name})")
    print(f"   SINCE {since_str}")
    print(f"   UNTIL {until_str}")
    print("   Executing NRQL via chartdata service...")

    products_nrql = (
        "SELECT count(*) AS 'Number of Views' "
        "FROM PageView "
        "WHERE pageUrl RLIKE '.*[0-9]+.*' "
        "FACET pageUrl "
        "ORDER BY count(*) "
        "LIMIT MAX "
        f"SINCE '{since_str}' "
        f"UNTIL '{until_str}' "
        f"WITH TIMEZONE '{timezone_name}'"
    )

    pages_nrql = (
        "SELECT count(*) AS 'Number of Views' "
        "FROM PageView "
        "FACET pageUrl "
        "ORDER BY count(*) "
        "LIMIT MAX "
        f"SINCE '{since_str}' "
        f"UNTIL '{until_str}' "
        f"WITH TIMEZONE '{timezone_name}'"
    )

    top_products = _run_nrql(base_url, headers, account_id_int, products_nrql)
    top_pages = _run_nrql(base_url, headers, account_id_int, pages_nrql)

    label = f"{query_date} ({timezone_name})"
    _annotate_timestamp(top_products, label)
    _annotate_timestamp(top_pages, label)

    html_block = _render_html(top_products, top_pages)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    wrapper = (
        "<!-- Generated by preview_page_views.py on "
        f"{generated_at} -->\n{html_block}"
    )

    output_path = args.output
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(wrapper)

    print(f"✅ Page Views HTML written to {output_path}")
    print("   Open this file in a browser or paste the markup into the GitHub Pages template.")


def _parse_arguments():
    parser = argparse.ArgumentParser(description="Generate Page Views HTML for a chosen date.")
    parser.add_argument("--account-id", help="New Relic account ID (overrides NEWRELIC_ACCOUNT_ID env).")
    parser.add_argument("--cookie", help="New Relic session cookie (overrides NEWRELIC_COOKIE env).")
    parser.add_argument("--date", help="Reporting date in YYYY-MM-DD format.")
    parser.add_argument("--timezone", default=DEFAULT_TIMEZONE,
                        help=f"Account timezone identifier (default: {DEFAULT_TIMEZONE}).")
    parser.add_argument("--base-url", help="Override NRQL endpoint URL.")
    parser.add_argument("--output", default="page_views_preview.html",
                        help="Path to write the generated HTML (default: page_views_preview.html).")
    return parser.parse_args()


def main():
    args = _parse_arguments()
    try:
        generate_preview(args)
    except requests.HTTPError as http_err:
        body = http_err.response.text[:500] if http_err.response is not None else ""
        print(f"❌ HTTP {http_err.response.status_code if http_err.response else 'Error'}: {http_err}")
        if body:
            print("Response body (truncated):")
            print(body)
    except Exception as exc:
        print(f"❌ Unexpected error: {exc}")


if __name__ == "__main__":
    main()