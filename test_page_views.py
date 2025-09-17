#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys
from pathlib import Path

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("Warning: python-dotenv not installed. Install with: pip install python-dotenv")
    print("Continuing with existing environment variables...")

ROOT = Path(__file__).resolve().parent


def ensure_sample_csvs(au_csv: Path, nz_csv: Path, product_csv: Path):
    if not au_csv.exists():
        au_csv.write_text("Timestamp,URL,Status,Path,Visible\n" \
                         "2025-01-01T00:00:00Z,https://www.kmart.com.au/,200,/,true\n",
                          encoding="utf-8")
    if not nz_csv.exists():
        nz_csv.write_text("Timestamp,URL,Status,Path,Visible\n" \
                         "2025-01-01T00:00:00Z,https://www.kmart.co.nz/,200,/,true\n",
                          encoding="utf-8")
    if not product_csv.exists():
        product_csv.write_text("SKU,ID,DETAIL\n" \
                              "12345678,NOT_FOUND,Placeholder - No product data\n",
                               encoding="utf-8")


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)


def main():
    parser = argparse.ArgumentParser(description="Generate Page Views (Top Products/Pages/Broken Links Views) and preview the report locally")
    parser.add_argument("--base-url", required=False, help="NEWRELIC_BASE_URL (full metadata URL required by newrelic_top_products.py)")
    parser.add_argument("--cookie", required=False, help="NEWRELIC_COOKIE header value (NR cookies)")
    parser.add_argument("--account-id", required=False, help="NEWRELIC_ACCOUNT_ID")
    parser.add_argument("--au-csv", default="au_link_check_results.csv", help="AU CSV path")
    parser.add_argument("--nz-csv", default="nz_link_check_results.csv", help="NZ CSV path")
    parser.add_argument("--product-csv", default="product_export.csv", help="Product CSV path")
    parser.add_argument("--output-html", default="combined_report.html", help="Output HTML path")

    args = parser.parse_args()

    # Set environment variables for newrelic_top_products.py from CLI args if provided (otherwise use .env file values)
    if args.base_url:
        os.environ["NEWRELIC_BASE_URL"] = args.base_url
    if args.cookie:
        os.environ["NEWRELIC_COOKIE"] = args.cookie
    if args.account_id:
        os.environ["NEWRELIC_ACCOUNT_ID"] = args.account_id
    
    # Display loaded environment variables (without exposing sensitive data)
    print("Environment variables loaded:")
    print(f"  NEWRELIC_BASE_URL: {'✓ Set' if os.environ.get('NEWRELIC_BASE_URL') else '✗ Missing'}")
    print(f"  NEWRELIC_COOKIE: {'✓ Set' if os.environ.get('NEWRELIC_COOKIE') else '✗ Missing'}")
    print(f"  NEWRELIC_ACCOUNT_ID: {os.environ.get('NEWRELIC_ACCOUNT_ID', '✗ Missing')}")
    print()

    # Brief sanity check without exposing secrets
    missing = [k for k in ("NEWRELIC_BASE_URL", "NEWRELIC_ACCOUNT_ID") if not os.environ.get(k)]
    if missing:
        print(f"Warning: missing required env vars: {', '.join(missing)}. The New Relic request may fail.")
    if not os.environ.get("NEWRELIC_COOKIE"):
        print("Note: NEWRELIC_COOKIE not provided; requests may fail if authentication is required.")

    # Ensure sample CSVs exist so report_generator can render
    au_csv = ROOT / args.au_csv
    nz_csv = ROOT / args.nz_csv
    product_csv = ROOT / args.product_csv
    ensure_sample_csvs(au_csv, nz_csv, product_csv)

    print("➡️ Generating Page Views via newrelic_top_products.py ...")
    nr = run([sys.executable, "newrelic_top_products.py"]) 
    if nr.returncode != 0:
        print("❌ newrelic_top_products.py failed:")
        print(nr.stderr)
    else:
        print("✅ newrelic_top_products.py completed")

    # Ensure we have a page_views_content.html (or fallback)
    pv_html = ROOT / "page_views_content.html"
    legacy = ROOT / "top_products_content.html"
    if not pv_html.exists() and legacy.exists():
        print("ℹ️ Page Views file missing, using legacy top_products_content.html as fallback")
        pv_html.write_text(legacy.read_text(encoding="utf-8"), encoding="utf-8")
    if not pv_html.exists():
        print("⚠️ Neither page_views_content.html nor legacy found; writing empty placeholder")
        pv_html.write_text("<p>No Page Views data available. Did the New Relic request succeed?</p>", encoding="utf-8")

    print("➡️ Building preview report via report_generator.py ...")
    out_html = ROOT / args.output_html
    rg = run([sys.executable, "report_generator.py",
              "--au-csv", str(au_csv.name),
              "--nz-csv", str(nz_csv.name),
              "--product-csv", str(product_csv.name),
              "--output-html", str(out_html.name)])

    # Surface report_generator output
    if rg.stdout:
        print(rg.stdout)
    if rg.returncode != 0:
        print("❌ report_generator.py failed:")
        print(rg.stderr)
        sys.exit(rg.returncode)

    if out_html.exists():
        print(f"✅ Preview ready: {out_html}")
    else:
        print("❌ Preview HTML was not created")
        sys.exit(1)


if __name__ == "__main__":
    main()