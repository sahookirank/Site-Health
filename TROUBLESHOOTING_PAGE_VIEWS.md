# Page Views Troubleshooting Guide

## Issue Summary

The `test_page_views.py` script was not displaying any data despite using correct API call parameters. The root cause was identified as an SSL/TLS configuration issue in the Python environment preventing HTTPS requests to the New Relic API.

## Root Cause Analysis

### 1. SSL Module Issue
```
ImportError: dlopen(.../_ssl.cpython-311-darwin.so, 0x0002): Library not loaded: /opt/homebrew/opt/openssl@1.1/lib/libssl.1.1.dylib
```

**Cause**: The Python installation is missing or has incorrectly linked OpenSSL libraries, preventing SSL/TLS connections.

### 2. Environment Variable Loading
- **Fixed**: Added `python-dotenv` integration to both `test_page_views.py` and `newrelic_top_products.py`
- **Result**: Environment variables now load correctly from `.env` file

### 3. API Request Failures
- **Symptom**: All New Relic API requests fail with SSL errors
- **Impact**: Empty data returned, resulting in tables showing "No data available"

## Solutions Implemented

### ✅ Immediate Fixes

1. **Environment Variable Loading**
   ```python
   # Added to both scripts
   try:
       from dotenv import load_dotenv
       load_dotenv()
   except ImportError:
       print("Warning: python-dotenv not installed")
   ```

2. **Mock Data Testing**
   - Created `test_newrelic_mock.py` for testing HTML generation
   - Verified that display logic works correctly with sample data
   - Confirmed the issue is API connectivity, not data processing

3. **Enhanced Debugging**
   - Added environment variable status display
   - Improved error reporting in API requests
   - Added detailed logging for troubleshooting

### 🔧 SSL Issue Solutions

#### Option 1: Reinstall Python with Proper SSL Support
```bash
# Using pyenv (recommended)
brew install openssl
export LDFLAGS="-L$(brew --prefix openssl)/lib"
export CPPFLAGS="-I$(brew --prefix openssl)/include"
pyenv install 3.11.0
pyenv global 3.11.0
```

#### Option 2: Use System Python
```bash
# Switch to system Python which typically has working SSL
/usr/bin/python3 -m pip install --user -r requirements.txt
/usr/bin/python3 test_page_views.py
```

#### Option 3: Docker Solution
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "test_page_views.py"]
```

## Verification Steps

### 1. Test Environment Variables
```bash
python test_page_views.py
# Should show:
# Environment variables loaded:
#   NEWRELIC_BASE_URL: ✓ Set
#   NEWRELIC_COOKIE: ✓ Set
#   NEWRELIC_ACCOUNT_ID: 1065151
```

### 2. Test SSL Connectivity
```bash
python -c "import ssl, requests; print('SSL OK'); requests.get('https://httpbin.org/get')"
```

### 3. Test with Mock Data
```bash
python test_newrelic_mock.py
# Should generate HTML with sample data
```

### 4. Verify HTML Generation
- Check `page_views_content.html` for data
- Verify tables show actual numbers, not "No data available"
- Confirm all three tabs (Top Products, Top Pages, Broken Links Views) have content

## Current Status

✅ **Fixed Issues:**
- Environment variable loading from `.env` file
- HTML generation and display logic
- Data processing and formatting
- Error reporting and debugging

⚠️ **Remaining Issue:**
- SSL/TLS connectivity preventing live API calls
- Requires Python environment fix or alternative approach

## Testing Results

### Mock Data Test
```
📊 Mock Data Preview:
Top Products:
  1. https://www.kmart.com.au/product/wireless-bluetooth-headphones-12345 - 1,250 views
  2. https://www.kmart.com.au/product/smart-watch-fitness-tracker-67890 - 980 views
  3. https://www.kmart.co.nz/product/kitchen-appliance-set-54321 - 750 views

Top Pages:
  1. https://www.kmart.com.au/ - 5,420 views
  2. https://www.kmart.com.au/category/electronics - 3,210 views
  3. https://www.kmart.co.nz/category/home-garden - 2,890 views
```

### HTML Output Verification
- ✅ Tables populate correctly with data
- ✅ Summary statistics calculate properly
- ✅ Interactive tabs function as expected
- ✅ Links and formatting display correctly

## Recommendations

1. **Immediate**: Fix SSL issue using one of the provided solutions
2. **Short-term**: Test with working Python environment
3. **Long-term**: Consider containerized deployment for consistency
4. **Monitoring**: Add health checks for API connectivity

## Files Modified

- `test_page_views.py` - Added dotenv loading and enhanced debugging
- `newrelic_top_products.py` - Added dotenv loading
- `requirements.txt` - Added python-dotenv dependency
- `test_newrelic_mock.py` - Created for testing (new file)
- `TROUBLESHOOTING_PAGE_VIEWS.md` - This documentation (new file)

The core functionality is working correctly; the only remaining issue is the SSL configuration in the Python environment.