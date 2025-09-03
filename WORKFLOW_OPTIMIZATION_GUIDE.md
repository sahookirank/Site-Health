# GitHub Workflow Optimization Guide

## Overview

The `broken-link-check.yml` workflow has been completely restructured to solve critical synchronization issues and provide flexibility. The workflow now supports two modes of operation with proper sequential execution:

1. **Full Mode** (default): Runs complete link checking + product fetching process (~1.5 hours)
2. **Fast Mode**: Skips link checking and product fetching, uses artifacts from previous successful runs

## 🔧 **CRITICAL FIX: Synchronization Issue Resolved**

### **Previous Problem**
- Link checkers ran and generated CSV files
- Product data fetch was triggered as a **separate workflow**
- Main workflow continued **immediately without waiting**
- Report generation failed because product CSV was missing
- GitHub Pages deployment was incomplete or failed

### **Solution Implemented**
- **Removed separate workflow trigger** for `product-data-fetch.yml`
- **Integrated product fetching inline** as sequential steps
- **Ensured proper execution order**: Link Checking → Product Fetching → Report Generation → Deployment
- **All CSV files are now available** before report generation

## New Features

### 1. Workflow Input Parameters

The workflow now accepts a boolean input parameter:

- **`skip_link_checks`**: 
  - Description: "Skip the time-consuming link checker steps and use artifacts from previous run"
  - Default: `false`
  - Type: `boolean`

### 2. Conditional Execution

Link checker steps now run conditionally:
- "Run AU Link Checker" - only runs when `skip_link_checks` is `false`
- "Run NZ Link Checker" - only runs when `skip_link_checks` is `false`

### 3. Artifact Retrieval Fallback

When `skip_link_checks` is `true`, the workflow:
1. Searches for the most recent successful workflow run
2. Downloads the `link-check-report` artifact containing CSV files
3. Extracts `au_link_check_results.csv` and `nz_link_check_results.csv`
4. Creates placeholder CSV files if artifacts are not found
5. Verifies all required files exist before proceeding

## Usage

### Scheduled Runs (Default Behavior)
- Runs automatically at 4PM UTC daily
- Executes full link checking process
- No changes to existing behavior

### Manual Trigger - Full Mode
```yaml
# Trigger via GitHub UI or API
workflow_dispatch:
  inputs:
    skip_link_checks: false  # or omit (defaults to false)
```

### Manual Trigger - Fast Mode
```yaml
# Trigger via GitHub UI or API
workflow_dispatch:
  inputs:
    skip_link_checks: true
```

## Benefits

1. **Time Savings**: Fast mode completes in minutes instead of ~1.5 hours
2. **Development Efficiency**: Quickly test report generation without waiting for link checks
3. **Resource Optimization**: Reduces compute usage for non-critical runs
4. **Backward Compatibility**: Existing scheduled runs continue unchanged

## Error Handling

The workflow includes robust error handling:
- Graceful fallback to placeholder data if artifacts are unavailable
- Verification steps to ensure required CSV files exist
- Detailed logging for troubleshooting
- Continues execution even if artifact download fails

## New Workflow Steps Overview

### **Full Mode** (schedule or manual with `skip_link_checks=false`)
1. **Setup** (checkout, Python, dependencies)
2. **Database Restoration** (from gh-pages)
3. **Run AU Link Checker** → generates `au_link_check_results.csv`
4. **Run NZ Link Checker** → generates `nz_link_check_results.csv`
5. **Setup Product Database** (create/initialize if needed)
6. **Install Product Fetch Dependencies**
7. **Create Product Fetch Script** (inline Python script)
8. **Run Product Data Fetch** → generates `product_export_*.csv`
9. **Generate Combined Report** (uses all 3 CSV files)
10. **Deploy to GitHub Pages** (complete report with all data)

### **Fast Mode** (manual with `skip_link_checks=true`)
1. **Setup** (checkout, Python, dependencies)
2. **Database Restoration** (from gh-pages)
3. **Download CSV Artifacts** (from previous successful run)
4. **Extract CSV Files** (AU, NZ link check results)
5. **Fetch Product Data Fallback** (use existing or create minimal data)
6. **Generate Combined Report** (uses all 3 CSV files)
7. **Deploy to GitHub Pages** (complete report with all data)

## Key Improvements

### ✅ **Synchronization Fixed**
- **Sequential execution**: All data generation completes before report generation
- **No more race conditions**: Product data is always available when needed
- **Reliable deployments**: GitHub Pages always gets complete reports

### ✅ **Integrated Product Fetching**
- **Inline execution**: Product fetching runs within the main workflow
- **Proper dependencies**: All required packages installed in sequence
- **Environment variables**: Secrets properly passed to product fetch steps
- **Fallback handling**: Graceful degradation when API tokens are unavailable

### ✅ **Enhanced Error Handling**
- **Conditional execution**: Steps run only when appropriate
- **Fallback data**: Minimal CSV files created if fetching fails
- **Comprehensive logging**: Better visibility into each step
- **File verification**: Ensures all required CSV files exist before proceeding

## Monitoring

To monitor the workflow:
- Check GitHub Actions tab for run status
- Review step logs for detailed execution information
- Verify CSV file presence in the "Verify CSV files exist" step
- Check artifact downloads in the "Download CSV artifacts" step

## Troubleshooting

If the fast mode fails to find artifacts:
1. Ensure at least one successful full run exists
2. Check that artifacts haven't expired (default: 90 days)
3. Verify the artifact name matches "link-check-report"
4. Review the workflow logs for specific error messages

The workflow will create placeholder CSV files as a last resort to ensure execution continues.
