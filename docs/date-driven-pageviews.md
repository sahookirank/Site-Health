# Date-Driven Page Views Refresh Design

## Overview
This design enables the GitHub Pages report to refresh “Top Products” and “Top Pages” with a selected reporting day while keeping New Relic credentials off the client. The flow relies on a lightweight proxy/serverless endpoint that executes NRQL and returns JSON data to the static site.

```
Browser (GitHub Pages) ──▶ Serverless Proxy ──▶ New Relic NRQL API
         ▲                        │
         └──── refreshed HTML ◀───┘
```

## Browser-Side Fetch Alternative

If you have a New Relic session cookie already stored in your browser profile and only need an internal preview, you can bypass a proxy altogether:

1. Open the GitHub Pages dashboard in the same browser where the cookie is valid.
2. Inject a script (via the built HTML) that reads the cookie and calls the NRQL endpoint directly using `fetch`. Example:

   ```html
   <script>
   async function fetchWithCookie(nrql) {
       const response = await fetch("https://chartdata.service.newrelic.com/v3/nrql?", {
           method: "POST",
           headers: {
               "Content-Type": "application/json",
               "Cookie": document.cookie  // relies on the session cookie already present
           },
           body: JSON.stringify({
               account_ids: [Number(window.NEWRELIC_ACCOUNT_ID)],
               nrql
           }),
           credentials: "include"
       });
       if (!response.ok) throw new Error(`NRQL request failed: ${response.status}`);
       return response.json();
   }
   </script>
   ```

3. Construct the `SINCE/UNTIL` clauses from the selected date and pass the NRQL string into `fetchWithCookie`. You still need a small JavaScript layer (date picker handler + DOM update) to invoke this helper and render the returned results; the API call alone is insufficient.

⚠️ **Security caveats**:
- Browsers block cross-site requests with custom `Cookie` headers; `credentials: "include"` works only if the cookie domain matches the NRQL host and CORS allows it.
- Surfacing raw session cookies inside client-side code exposes them to anyone with access to the page. Anyone loading the GitHub Pages site would see or copy the session value, effectively compromising your New Relic account.
- GitHub Pages must serve over HTTPS to avoid mixed-content blocks.
- GitHub Pages cannot set or rotate private session cookies on behalf of viewers; only individuals who already have the New Relic cookie in their browser can use this flow.

Because GitHub Pages is static, your cookie stays in GitHub Actions secrets and is used only when `newrelic_top_products.py` runs during the build. That job emits static HTML with embedded counts; the browser never inherits the cookie. Introducing a date picker means fetching fresh NRQL results after the page loads, which a static site cannot do without exposing credentials. Hence, either all dates must be pre-rendered during the workflow run, or a runtime proxy (or manual local preview) must relay authenticated requests on demand.

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

### Example: AWS Lambda + API Gateway Walkthrough

1. **Bootstrap the function locally**

   ```bash
   mkdir nrql-proxy && cd nrql-proxy
   python -m venv .venv && source .venv/bin/activate
   pip install requests
   cat > lambda_function.py <<'PY'
   import json
   import os
   import requests

   BASE_URL = os.environ["NEWRELIC_BASE_URL"]
   ACCOUNT_ID = int(os.environ["NEWRELIC_ACCOUNT_ID"])
   COOKIE = os.environ["NEWRELIC_COOKIE"]
   API_KEY = os.environ["INTERNAL_API_KEY"]

   def handler(event, context):
       if event.get("headers", {}).get("x-api-key") != API_KEY:
           return {"statusCode": 403, "body": "Forbidden"}

       try:
           body = json.loads(event.get("body") or "{}")
       except json.JSONDecodeError:
           return {"statusCode": 400, "body": "Invalid JSON"}

       nrql = body.get("nrql")
       if not nrql:
           return {"statusCode": 400, "body": "Missing NRQL"}

       payload = {"account_ids": [ACCOUNT_ID], "nrql": nrql}
       headers = {
           "Content-Type": "application/json",
           "Cookie": COOKIE,
       }

       try:
           resp = requests.post(BASE_URL, headers=headers, json=payload, timeout=15)
       except requests.RequestException as exc:
           return {"statusCode": 502, "body": f"Upstream error: {exc}"}

       return {
           "statusCode": resp.status_code,
           "body": resp.text,
           "headers": {"Content-Type": "application/json"}
       }
   PY

   zip function.zip lambda_function.py
   ```

2. **Create the Lambda function**

   - In AWS Console: *Lambda → Create function → Author from scratch*.
   - Runtime: Python 3.10.
   - Upload `function.zip` as the deployment package.
   - Set environment variables:
     | Key | Value |
     |-----|-------|
     | `NEWRELIC_BASE_URL` | `https://chartdata.service.newrelic.com/v3/nrql?` |
     | `NEWRELIC_ACCOUNT_ID` | Your account ID |
     | `NEWRELIC_COOKIE` | Store in AWS Secrets Manager and reference via Lambda (e.g., using a Lambda environment variable wired to the secret) |
     | `INTERNAL_API_KEY` | A long random string (e.g., generated with `openssl rand -hex 32`) |

3. **Attach the secret securely**

   - Use AWS Secrets Manager to store the cookie.
   - Grant the Lambda execution role permission (`secretsmanager:GetSecretValue`).
   - Replace `COOKIE = os.environ["NEWRELIC_COOKIE"]` with a `boto3` lookup if you prefer not to keep the secret in plain env vars.

4. **Expose through API Gateway**

   - Create an *HTTP API → Integrations → Add Lambda integration*.
   - Route: `POST /api/pageviews`.
   - Enable CORS, limiting allowed origins to `https://<your-org>.github.io`.
   - Create an API key, attach it to a usage plan, and require it for this route.

5. **Frontend fetch**

   ```js
   async function fetchViaProxy(nrql) {
       const response = await fetch("https://<api-id>.execute-api.<region>.amazonaws.com/api/pageviews", {
           method: "POST",
           headers: {
               "Content-Type": "application/json",
               "x-api-key": "<frontend-shared-key>"
           },
           body: JSON.stringify({ nrql })
       });
       if (!response.ok) throw new Error(`Proxy failed: ${response.status}`);
       return response.json();
   }
   ```

6. **Operational safeguards**

   - Rotate `INTERNAL_API_KEY` and the New Relic cookie regularly.
   - Monitor CloudWatch logs for unusual traffic.
   - Apply throttling on the usage plan to prevent abuse.
   - Consider adding payload validation (date ranges, regex) before forwarding.

You can translate the same pattern to Cloudflare Workers, Azure Functions, or Vercel/Netlify by mapping the environment variables, adding an API-key check, and forwarding the NRQL POST request.

### Zero-Cost (or Near-Zero) Paths

1. **Cloudflare Workers (free tier)**
   - Cloudflare’s free plan includes generous request quotas. Deploy a Worker with the same proxy logic:
     ```js
     export default {
       async fetch(request, env) {
         if (request.headers.get("x-api-key") !== env.INTERNAL_API_KEY) {
           return new Response("Forbidden", { status: 403 });
         }
         const { nrql } = await request.json();
         if (!nrql) return new Response("Missing NRQL", { status: 400 });

         const upstream = await fetch(env.NEWRELIC_BASE_URL, {
           method: "POST",
           headers: {
             "Content-Type": "application/json",
             "Cookie": env.NEWRELIC_COOKIE
           },
           body: JSON.stringify({
             account_ids: [Number(env.NEWRELIC_ACCOUNT_ID)],
             nrql
           })
         });

         return new Response(upstream.body, {
           status: upstream.status,
           headers: { "Content-Type": "application/json" }
         });
       }
     };
     ```
   - Store secrets with `wrangler secrets put`, and set `INTERNAL_API_KEY`, `NEWRELIC_COOKIE`, etc. No hosting fees unless you exceed free usage.

2. **Local reverse proxy + tunnel (ad hoc testing)**
   - Run a local FastAPI/Flask app that forwards NRQL calls using your credentials.
   - Use a free tunnel (e.g., `cloudflared tunnel run`, `ssh -R`, `localtunnel`) to expose it temporarily.
   - Point the GitHub Pages fetch URL to that tunnel during testing, then tear it down to keep secrets safe.

3. **Local-only workflow**
   - Instead of publishing dynamic data, run `preview_page_views.py` whenever you need a dated snapshot.
   - Paste the generated HTML block into the static report. Zero hosting cost, but manual refresh.

Choose the option that fits your security comfort and budget; both Cloudflare Workers and ephemeral tunnels avoid ongoing charges.

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

## Local Preview Without Publishing

You can validate the Page Views tab offline:

1. Checkout this feature branch and run:
   ```bash
   python preview_page_views.py --account-id <ID> --date 2025-10-08
   ```
   Supply your New Relic cookie when prompted. The script writes `page_views_preview.html`.

2. Review the markup by opening the file directly in a browser, or serve it locally:
   ```bash
   python -m http.server --directory .
   ```
   Then visit `http://localhost:8000/page_views_preview.html`.

3. Copy the generated block into `page_views_content.html` for manual inspection in the broader report layout if needed. No GitHub Pages deployment is required.

## Implementation Steps

5. Copy the generated block into `page_views_content.html` for manual inspection in the broader report layout if needed. No GitHub Pages deployment is required.

## Dry-Run the JSON Cache Locally

1. Export the same secrets the GitHub runner would use (or create a `.env` and `source` it):
   ```bash
   export NEWRELIC_COOKIE="NR_SESSION=..."
   export NEWRELIC_ACCOUNT_ID=123456
   ```
2. Execute the Node fetcher for a specific date:
   ```bash
   node scripts/fetch_page_views.js --date 2025-10-08 --out tmp/page_views.json
   ```
3. Inspect `tmp/page_views.json` and point `preview_page_views.py` (or another local renderer) to that file to confirm the shape matches what the frontend expects.
4. Re-run for additional dates if desired, then commit the JSON (or keep it ignored) before letting CI reuse the same script during the workflow.
1. Build and deploy the serverless proxy with NR credentials.
2. Add environment-protected API key for client access.
3. Update the GitHub Pages HTML/JS to include the date picker and fetch logic.
4. Parse JSON responses and render tables dynamically.
5. Test with multiple dates to ensure SINCE/UNTIL windows align with Melbourne time.
6. Document operational runbook (rotating credentials, monitoring).
