# GitHub Workflow Optimization Guide

## Overview

The `broken-link-check.yml` workflow has been optimized to provide flexibility and efficiency when running link checks. The workflow now supports two modes of operation:

1. **Full Mode** (default): Runs complete link checking process (~1.5 hours)
2. **Fast Mode**: Skips link checking and uses artifacts from previous successful runs

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

## Workflow Steps Overview

1. **Setup** (always runs)
2. **Link Checking** (conditional - only if `skip_link_checks` is `false`)
3. **Artifact Retrieval** (conditional - only if `skip_link_checks` is `true`)
4. **CSV Verification** (always runs)
5. **Product Data Fetch** (always runs)
6. **Report Generation** (always runs)
7. **Deployment** (always runs)

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
