#!/usr/bin/env node

/**
 * Fetch PageView aggregates for a specific date using New Relic NRQL.
 * 
 * This script is intended to run inside GitHub Actions (or another trusted CI environment)
 * where sensitive credentials are available as environment variables. It writes the raw API
 * response and parsed aggregates to disk so the static frontend can consume them later
 * without exposing secrets.
 * 
 * Usage:
 *   node scripts/fetch_page_views.js --date 2025-10-08 --timezone Australia/Melbourne --out data/page_views.json
 * 
 * Required environment variables:
 *   - NEWRELIC_COOKIE
 *   - NEWRELIC_ACCOUNT_ID
 * 
 * Optional environment variables:
 *   - NEWRELIC_BASE_URL (defaults to https://chartdata.service.newrelic.com/v3/nrql?)
 */

const fs = require("node:fs");
const path = require("node:path");

const fetch = global.fetch || ((...args) =>
    import("node-fetch").then(({ default: nodeFetch }) => nodeFetch(...args))
);

const DEFAULT_BASE_URL = "https://chartdata.service.newrelic.com/v3/nrql?";
const DEFAULT_TIMEZONE = "Australia/Melbourne";

function parseArgs() {
    const args = process.argv.slice(2);
    const options = {};
    for (let i = 0; i < args.length; i += 1) {
        const arg = args[i];
        if (arg.startsWith("--")) {
            const key = arg.slice(2);
            const value = args[i + 1];
            options[key] = value;
            i += 1;
        }
    }
    return options;
}

function ensure(value, name) {
    if (!value) {
        throw new Error(`Missing required ${name}`);
    }
    return value;
}

function formatDateWindow(date, timezone) {
    const since = `${date} 00:00:00`;
    const until = `${getNextDay(date)} 00:00:00`;
    return { since, until, timezone };
}

function getNextDay(dateStr) {
    const parts = dateStr.split("-").map(Number);
    if (parts.length !== 3 || parts.some(Number.isNaN)) {
        throw new Error(`Invalid date: ${dateStr}`);
    }
    const [year, month, day] = parts;
    const utcDate = new Date(Date.UTC(year, month - 1, day));
    const nextUtc = new Date(utcDate.getTime() + 24 * 60 * 60 * 1000);
    return nextUtc.toISOString().slice(0, 10);
}

function buildNrqlQueries({ since, until, timezone }) {
    const windowClause = `SINCE '${since}' UNTIL '${until}' WITH TIMEZONE '${timezone}'`;
    const products = [
        "SELECT count(*) AS 'Number of Views'",
        "FROM PageView",
        "WHERE pageUrl RLIKE '.*[0-9]+.*'",
        "FACET pageUrl",
        "ORDER BY count(*)",
        "LIMIT MAX",
        windowClause
    ].join(" ");

    const pages = [
        "SELECT count(*) AS 'Number of Views'",
        "FROM PageView",
        "FACET pageUrl",
        "ORDER BY count(*)",
        "LIMIT MAX",
        windowClause
    ].join(" ");

    return { products, pages };
}

async function fetchNrql(baseUrl, cookie, accountId, nrql) {
    const payload = {
        account_ids: [Number(accountId)],
        nrql
    };

    const response = await fetch(baseUrl, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "Cookie": cookie,
            "Accept": "application/json"
        },
        body: JSON.stringify(payload)
    });

    if (!response.ok) {
        const text = await response.text();
        throw new Error(`NRQL request failed (${response.status}): ${text}`);
    }

    return response.json();
}

function extractSeries(json) {
    if (!json) return [];
    if (Array.isArray(json)) return json;
    if (json.data?.actor?.nrql?.results) return json.data.actor.nrql.results;
    if (json.results) return json.results;
    return [];
}

function parseResults(series) {
    const now = new Date().toISOString();
    return series
        .filter(item => item?.facet || item?.name)
        .map(item => ({
            url: (item.facet || item.name || "").trim(),
            count: Number(item.count ?? item?.results?.[0]?.count ?? 0),
            timestamp: now
        }))
        .filter(item => item.url && item.url.toLowerCase() !== "other");
}

async function main() {
    try {
        const options = parseArgs();
        const date = ensure(options.date, "--date");
        const timezone = options.timezone || DEFAULT_TIMEZONE;
        const outputFile = options.out || path.join("data", `page_views_${date}.json`);

        const cookie = ensure(process.env.NEWRELIC_COOKIE, "NEWRELIC_COOKIE env");
        const accountId = ensure(process.env.NEWRELIC_ACCOUNT_ID, "NEWRELIC_ACCOUNT_ID env");
        const baseUrl = process.env.NEWRELIC_BASE_URL || DEFAULT_BASE_URL;

        const window = formatDateWindow(date, timezone);
        const queries = buildNrqlQueries(window);

        console.log(`Fetching New Relic PageView data for ${date} (${timezone})`);
        console.log(`SINCE ${window.since} UNTIL ${window.until}`);

        const [productsRaw, pagesRaw] = await Promise.all([
            fetchNrql(baseUrl, cookie, accountId, queries.products),
            fetchNrql(baseUrl, cookie, accountId, queries.pages)
        ]);

        const productsParsed = parseResults(extractSeries(productsRaw));
        const pagesParsed = parseResults(extractSeries(pagesRaw));

        const payload = {
            date,
            timezone,
            generatedAt: new Date().toISOString(),
            queries,
            products: {
                raw: productsRaw,
                rows: productsParsed
            },
            pages: {
                raw: pagesRaw,
                rows: pagesParsed
            }
        };

        fs.mkdirSync(path.dirname(outputFile), { recursive: true });
        fs.writeFileSync(outputFile, JSON.stringify(payload, null, 2), "utf8");

        console.log(`Wrote PageView data to ${outputFile}`);
        console.log(`Products rows: ${productsParsed.length}`);
        console.log(`Pages rows: ${pagesParsed.length}`);
    } catch (error) {
        console.error("❌ Failed to fetch PageView data:", error.message);
        process.exitCode = 1;
    }
}

if (require.main === module) {
    main();
}