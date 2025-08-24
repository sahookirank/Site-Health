# Kmart Broken Link Validator

This project contains scripts to check for broken links on the Kmart Australia (AU) and Kmart New Zealand (NZ) websites. It generates an HTML report detailing the status of checked links.

## Project Structure

- `au_link_checker.py`: Python script to crawl the Kmart AU website (starting from `https://www.kmart.com.au/`). It identifies links, checks their HTTP status, and saves the results to `au_link_check_results.csv`.
- `nz_link_checker.py`: Python script similar to `au_link_checker.py`, but for the Kmart NZ website (starting from `https://www.kmart.co.nz/`). It saves results to `nz_link_check_results.csv`.
- `report_generator.py`: Python script that takes `au_link_check_results.csv` and `nz_link_check_results.csv` as input and generates a combined HTML report (`combined_report.html`) with separate tabs for AU and NZ results.
  - Now also persists daily broken links into a SQLite database `broken_links.db` with per-day tables (e.g., `broken_links_2025_08_23`), enforces a 60-day retention policy, and adds a third "Changes" tab comparing today's broken links versus yesterday and 7 days ago.
- `requirements.txt`: Lists the Python dependencies (`requests`, `beautifulsoup4`, `pandas`). Includes a note on pinning versions for security and reproducibility.
- `.github/workflows/broken-link-check.yml`: GitHub Actions workflow that automates the link checking and reporting process.

## How to Run Locally

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd broken-link-validator
    ```

2.  **Set up a Python virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Run the link checkers:**
    - **Run Link Checkers (generates CSV files):**
      - For Kmart AU:
        ```bash
        python au_link_checker.py [--max-urls 100]
        ```
        This will generate `au_link_check_results.csv`.

      - For Kmart NZ:
        ```bash
        python nz_link_checker.py [--max-urls 100]
        ```
        This will generate `nz_link_check_results.csv`.

    - **Generate Combined HTML Report:**
      After running both checkers, you can generate the combined HTML report:
      ```bash
      python report_generator.py --au-csv au_link_check_results.csv --nz-csv nz_link_check_results.csv --output-html combined_report.html
      ```
      This will create `combined_report.html` (or your specified output file). You can open this file in a web browser to view the results.

### Quick local test (small crawl + synthetic changes)

Run the included `test_runner.py` to crawl a small subset (100 URLs per site), build the report, seed synthetic "yesterday" and "7 days ago" snapshots into `broken_links.db`, and regenerate the report so the "Changes" tab shows additions/removals:

```bash
python test_runner.py
```

Artifacts:
- `index.html` – final report with AU, NZ, and Changes tabs.
- `broken_links.db` – SQLite database with daily snapshots and 60-day retention.

## GitHub Actions Workflow

The workflow (`.github/workflows/broken-link-check.yml`) is configured to run:
- On a schedule (daily at 2 PM UTC).
- On push or pull request to the `main` branch.
- Manually via `workflow_dispatch`.

It then performs the following steps:

*(Note: While using a virtual environment is recommended for local development, GitHub Actions runners provide an isolated environment for each job. Therefore, explicitly creating a virtual environment within the workflow steps is generally not necessary, as dependencies are installed into this isolated job environment.)*

- Check out the repository.
- Set up Python 3.10.
- Install dependencies from `requirements.txt`.
- Run `au_link_checker.py` to generate `au_link_check_results.csv`.
- Run `nz_link_checker.py` to generate `nz_link_check_results.csv`.
- Retrieve existing `broken_links.db` from the `gh-pages` branch (if present) to maintain persistence between runs.
- Run `report_generator.py` to create `combined_report.html` from the two CSV files and persist today's broken links into `broken_links.db`. A 60-day retention policy is enforced.
- Rename `combined_report.html` to `index.html`.
- Upload the `index.html` and `broken_links.db` as an artifact `link-check-report`.
- Deploy `index.html` and `broken_links.db` to the `gh-pages` branch, making the combined report and DB available via GitHub Pages.

### SQLite data model

- Database file: `broken_links.db`
- Per-day table: `broken_links_YYYY_MM_DD` with columns: `Region, URL, Status, Path, Visible, Timestamp`.
- Retention: tables older than 60 days are dropped during each report generation.

### Changes tab

- Shows differences in broken links (by `Region, URL`) versus:
  - Yesterday
  - 7 days ago
- Two sections each: Added and Removed.
