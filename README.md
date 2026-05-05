# Review Analytics Engine

## What It Does

Review Analytics Engine helps Amazon sellers compare one listing against competitors, extract customer buying criteria from reviews, estimate monthly revenue from BSR, and generate optimized listing copy.

It is built as a practical decision dashboard: scrape data, analyze customer language, and turn insights into copy updates.

## Features

- Multi-competitor product comparison
- BSR-based monthly revenue estimation
- AI(claude API) purchase-criteria analysis
- Customer hook extraction (repeat phrases + sentiment)
- AI(claude API)-generated listing rewrite (title, bullets, description)

## Tech Stack

- Frontend: React + Tailwind + Recharts
- Backend: FastAPI (Python)
- AI: Anthropic Claude
- Scraping: Bright Data
- Storage: SQLite

## How To Use (Deployed Demo)

1. Open the deployed dashboard URL.https://review-analytics-pixii-zeta.vercel.app/
2. Paste your main Amazon product URL.
3. Paste up to 9 competitor URLs.
4. Start scrape job.
5. Review results in:
   - `Competitive Overview`
   - `Purchase Criteria`
   - `Customer Hooks`
   - `Generated Listing`
6. If live scraping is delayed, click `View existing dashboard` to show stored demo results.

## Demo Dataset (Whey Protein)

- Main ASIN: `B002DYIZHG`
- Competitors: `B099J2SWXV`, `B00XIKPUK4`, `B0CQ32D39X`, `B071JG5QYT`, `B01KITQG0A`, `B09SYB2ZQ2`, `B0BDTMHBC8`, `B07FHPGS4V`
- Amazon URL pattern: `https://www.amazon.com/dp/<ASIN>`

## Demo Constraints

- **Review cap:** This demo intentionally processes **100 reviews per product** due to Bright Data budget constraints.
- **Scrape time variability:** Bright Data job completion is unpredictable and may vary from roughly **10 to 30 minutes** depending on queue/load and ASIN behavior.
- **Fallback behavior:** If live backend fetch fails in demo, the UI can show seeded whey-protein demo data for presentation continuity.

## Notes

- Revenue values are directional estimates from BSR buckets, not exact Amazon sales figures.
- Long-running scrape/analysis jobs can fail intermittently due to third-party API limits/timeouts; the dashboard surfaces job status and errors.
