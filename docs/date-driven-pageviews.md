# Date-Driven Page Views Refresh Design

## Overview
This design enables the GitHub Pages report to refresh “Top Products” and “Top Pages” with a selected reporting day while keeping New Relic credentials off the client. The flow relies on a lightweight proxy/serverless endpoint that executes NRQL and returns JSON data to the static site.

```
Browser (GitHub Pages) ──▶ Serverless Proxy ──▶ New Relic NRQL API
         ▲                        │
         └──── refreshed HTML ◀───┘
```

## Serverless Proxy Contract

| Item            | Details |
|-----------------|---------|
| Method          | `POST` |
| Path            | `/api/pageviews` (example) |
| Auth            | API key (via header, e.g., `x-api-key`) |
| Body (JSON)     | `{ "date": "2025-10-08", "timezone": "Australia/Melbourne" }` |
| Response (JSON) | `{ "topProducts": [...], "topPages": [...] }` |

### NRQL template

```
SELECT count(*) AS 'Number of Views'
FROM PageView
WHERE pageUrl RLIKE '.*[0-9]+.*'
FACET pageUrl
ORDER BY count(*)
LIMIT MAX
SINCE '{DATE} 00:00:00 +11:00'
UNTIL '{DATE_NEXT} 00:00:00 +11:00'
WITH TIMEZONE '{TIMEZONE}'
```

Use the same SINCE/UNTIL block for the Top Pages query but drop the `pageUrl` regex filter.

### Proxy responsibilities
1. Validate and parse the incoming date (ISO `YYYY-MM-DD`).
2. Derive the end date as `date + 1 day`.
3. Substitute `SINCE`/`UNTIL` placeholders in both NRQL statements.
4. Forward requests to `https://chartdata.service.newrelic.com/v3/nrql?` with the stored headers and credentials.
5. Normalize results into arrays of `{ "url": string, "count": number, "timestamp": string }`.
6. Return JSON with separate arrays for products and pages.
7. Enforce rate limiting and check API key.

Store New Relic credentials (cookie, account ID, base URL) as secure environment variables within the serverless platform (e.g., AWS Lambda + API Gateway, Cloudflare Workers, Azure Functions).

## GitHub Pages UI Updates

1. **Date picker**  
   - Add a single-day picker (e.g., `<input type="date" id="pvDate">`) defaulting to the latest available day.  
   - Optionally constrain `min`/`max` attributes to valid history.

2. **Fetch logic**  
   ```js
   async function refreshPageViews(selectedDate) {
       const body = { date: selectedDate, timezone: 'Australia/Melbourne' };
       const response = await fetch('https://your-proxy.example.com/api/pageviews', {
           method: 'POST',
           headers: {
               'Content-Type': 'application/json',
               'x-api-key': '<public-safe key if required>'
           },
           body: JSON.stringify(body)
       });
       if (!response.ok) throw new Error('Proxy request failed');
       return response.json();
   }
   ```

3. **DOM refresh**  
   - Rebuild the “Top Products” and “Top Pages” tables from the JSON payload.  
   - Display a loading spinner and error banner as needed.

4. **Graceful fallback**  
   - If the proxy returns an error, retain existing data and surface a message.

## Deployment Notes

- Host the proxy in a region close to New Relic.  
- Configure CORS to allow the GitHub Pages origin.  
- Ensure the proxy times out quickly and returns friendly errors.  
- Log requests (without leaking secrets) for troubleshooting.

## Implementation Steps

1. Build and deploy the serverless proxy with NR credentials.  
2. Add environment-protected API key for client access.  
3. Update the GitHub Pages HTML/JS to include the date picker and fetch logic.  
4. Parse JSON responses and render tables dynamically.  
5. Test with multiple dates to ensure SINCE/UNTIL windows align with Melbourne time.  
6. Document operational runbook (rotating credentials, monitoring).
