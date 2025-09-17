# Page Views Integration Feature Branch

This feature branch (`feature/page-views-integration`) contains the complete Page Views integration with New Relic API. It's designed to be fully functional and independently deployable for testing purposes.

## 🚀 What's New

### Enhanced Features
- **Page Views Tab**: New tab in the report with three sub-sections:
  - Top Products (from New Relic NRQL queries)
  - Top Pages (from New Relic NRQL queries) 
  - Broken Links Views (combines broken links data with page view metrics)

### Technical Improvements
- **Secure Credential Handling**: Environment variable-based authentication
- **Robust Error Handling**: Graceful fallbacks when API calls fail
- **Enhanced CSV Reading**: Case-insensitive URL column detection
- **Subprocess Reliability**: Uses `sys.executable` and inherits environment

## 🧪 Testing the Feature Branch

### Prerequisites
1. New Relic account with dashboard access
2. Valid authentication cookie from New Relic session
3. Account ID and base URL from New Relic dashboard

### Local Testing

```bash
# Set your credentials (replace with actual values)
export NEWRELIC_BASE_URL="https://one.newrelic.com/dashboards/detail/YOUR_DASHBOARD_URL"
export NEWRELIC_COOKIE="your_full_cookie_header"
export NEWRELIC_ACCOUNT_ID="your_account_id"

# Run the test harness
python3 test_page_views.py

# Or run comprehensive deployment tests
python3 test_deployment.py \
  --base-url "$NEWRELIC_BASE_URL" \
  --cookie "$NEWRELIC_COOKIE" \
  --account-id "$NEWRELIC_ACCOUNT_ID" \
  --repo-url "https://github.com/sahookirank/Link-Checker"
```

### GitHub Pages Deployment

This branch is configured to automatically deploy to GitHub Pages when pushed. The deployment:

1. **Triggers automatically** on push to `feature/page-views-integration`
2. **Runs the full workflow** including artifact collection and report generation
3. **Deploys to a preview URL** for testing
4. **Mirrors production environment** as closely as possible

### Validation Checklist

- [ ] **API Connectivity**: New Relic API responds successfully
- [ ] **Data Retrieval**: Top Products, Top Pages, and Broken Links data populate
- [ ] **Report Generation**: `combined_report.html` is created successfully
- [ ] **UI Functionality**: All tabs render correctly with DataTables interactions
- [ ] **Error Handling**: Graceful fallbacks when credentials are missing/invalid
- [ ] **GitHub Pages**: Deployment succeeds and site is accessible

## 📁 Key Files Modified/Added

### Core Functionality
- `newrelic_top_products.py` - Enhanced with Page Views data fetching
- `report_generator.py` - Updated subprocess handling and environment inheritance
- `test_page_views.py` - New test harness for secure credential handling

### Testing & Deployment
- `test_deployment.py` - Comprehensive deployment validation script
- `.github/workflows/deploy-gh-pages.yml` - Updated to support feature branch deployment

### Generated Content
- `page_views_content.html` - Generated Page Views tab content
- `combined_report.html` - Complete report with all tabs

## 🔒 Security Considerations

- **No hardcoded credentials** in any committed files
- **Environment variable-based** authentication
- **Masked sensitive data** in logs and outputs
- **Secure subprocess execution** with inherited environment

## 🔄 Merge Process

Once all tests pass and functionality is validated:

1. **Create Pull Request** from `feature/page-views-integration` to `main`
2. **Review changes** and ensure no sensitive data is committed
3. **Verify deployment** works correctly in the feature branch
4. **Merge to main** to make changes live in production

## 🐛 Troubleshooting

### Empty Page Views Data
- Verify `NEWRELIC_BASE_URL` is the full dashboard metadata URL
- Check that `NEWRELIC_COOKIE` includes all required authentication tokens
- Ensure `NEWRELIC_ACCOUNT_ID` matches the account in the dashboard URL
- Confirm the New Relic session hasn't expired

### Deployment Issues
- Check GitHub Actions logs for detailed error messages
- Verify the workflow has proper permissions for Pages deployment
- Ensure all required files are committed and pushed

### Local Testing Problems
- Use `python3 -m http.server 8000` to serve the report locally
- Check browser console for JavaScript errors
- Verify all CSV files have the expected URL column format

## 📞 Support

For issues with this feature branch:
1. Check the deployment test results
2. Review GitHub Actions workflow logs
3. Validate credentials and API connectivity
4. Ensure all dependencies are properly installed