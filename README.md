# Review Analytics Engine

## What It Does

Review Analytics Engine helps Amazon sellers understand why customers buy, how competitors position their products, and what language should be reused in higher-converting listings. It scrapes product and review data, estimates monthly revenue from BSR, extracts purchase criteria and customer hooks with Claude, and presents the results in a React dashboard.

## Features

- Multi-competitor analysis
- AI-powered purchase criteria extraction
- Revenue estimation
- Customer hook mining
- AI-generated listing optimization

## Tech Stack

- Frontend: React + Tailwind
- Backend: Python + FastAPI
- Analysis: Claude API
- Database: SQLite
- Scraping: Bright Data / Playwright
- Charts: Recharts
- Icons: Lucide React

## Setup Instructions

### Prerequisites

- Python 3.9+
- Node.js 18+
- npm
- Claude API key
- Bright Data API key OR Playwright

### Installation

1. Clone/open the project and create your local environment file:

   ```bash
   cp .env.example .env
   ```

2. Add API keys to `.env`:

   ```env
   ANTHROPIC_API_KEY=your_claude_key
   CLAUDE_MODEL=claude-sonnet-4-20250514

   BRIGHT_DATA_API_KEY=your_bright_data_key
   BRIGHT_DATA_AMAZON_PRODUCT_DATASET_ID=gd_l7q7dkf244hwjntr0
   BRIGHT_DATA_AMAZON_REVIEWS_DATASET_ID=gd_le8e811kzy4ggddlq

   VITE_API_URL=http://localhost:8000
   ```

3. Install backend dependencies:

   ```bash
   python3 -m venv backend/.venv
   source backend/.venv/bin/activate
   pip install -r requirements.txt
   ```

4. Install frontend dependencies:

   ```bash
   npm install
   npm install --prefix frontend
   ```

### Usage

Run the FastAPI backend:

```bash
backend/.venv/bin/uvicorn backend.api:app --reload --port 8000
```

Run the React dashboard:

```bash
npm run dev --prefix frontend
```

Open:

```text
http://127.0.0.1:5173/
```

Primary workflow:

1. Open the dashboard.
2. Paste your Amazon listing URL.
3. Paste up to 9 competitor Amazon URLs.
4. Click `Scrape URLs`.
5. Wait for scraping to finish, then review the dashboard tabs.

Scrape one product:

```bash
backend/.venv/bin/python backend/scraper.py B000BD0RT0
```

Scrape one product plus competitors:

```bash
backend/.venv/bin/python backend/scraper.py B07JZHXXBT --competitors B000BD0RT0 B07FK237C5 B07QCY5ZYH B07FK28Z98 B07TWKR3X1 B01HCVVX76 B07FK25HFB B07FKCKQ9P B07FK3GJ8Q
```

Estimate revenue:

```bash
backend/.venv/bin/python backend/revenue_estimator.py
```

Analyze reviews with Claude:

```bash
backend/.venv/bin/python backend/analyzer.py --model claude-sonnet-4-20250514
```

Generate optimized listing copy:

```bash
backend/.venv/bin/python backend/listing_generator.py B000BD0RT0
```

## API Endpoints

### `GET /api/products`

Returns the 10-product competitive set with product fields and revenue estimates.

Response fields include:

```json
{
  "asin": "B000BD0RT0",
  "product": "Doctor's Best High Absorption Magnesium...",
  "price": 20.99,
  "rating": 4.6,
  "reviews": 75298,
  "bsr": "7",
  "estimated_units_per_month": 8000,
  "estimated_revenue_per_month": 167920.0,
  "revenue_confidence": "high",
  "is_main": false,
  "status": "Scraped"
}
```

### `GET /api/criteria`

Returns the top 5 purchase criteria and product scores for each criterion.

```json
[
  {
    "id": 1,
    "name": "effectiveness",
    "description": "Customers evaluate whether the supplement delivers promised benefits.",
    "mentionCount": 40,
    "scores": [
      { "asin": "B000BD0RT0", "product": "Doctor's Best...", "score": 8.0 }
    ]
  }
]
```

### `GET /api/hooks`

Returns customer hooks sorted by frequency.

Query params:

- `sentiment`: `positive`, `negative`, or `neutral`
- `min_frequency`: minimum frequency count

Example:

```bash
curl "http://localhost:8000/api/hooks?sentiment=positive&min_frequency=5"
```

### `GET /api/listing/{asin}`

Returns current and generated listing copy for side-by-side comparison.

```json
{
  "asin": "B000BD0RT0",
  "current": {
    "title": "Current title",
    "bullets": [],
    "description": "Current description"
  },
  "generated": {
    "title": "Optimized title",
    "bullets": ["Bullet 1", "Bullet 2"],
    "description": "Optimized description"
  }
}
```

### `POST /api/scrape`

Starts an async scrape job.

Request:

```json
{
  "asins": ["B000BD0RT0", "B07FK237C5"]
}
```

Response:

```json
{
  "job_id": "uuid",
  "status": "queued",
  "asins": ["B000BD0RT0", "B07FK237C5"]
}
```

### `POST /api/scrape-urls`

Starts an async scrape job from one product URL and up to 9 competitor URLs.

Request:

```json
{
  "product_url": "https://www.amazon.com/dp/B000BD0RT0",
  "competitor_urls": [
    "https://www.amazon.com/dp/B0CHHSFMRL"
  ]
}
```

Response:

```json
{
  "job_id": "uuid",
  "status": "queued",
  "asins": ["B000BD0RT0", "B0CHHSFMRL"]
}
```

### `GET /api/scrape/{job_id}`

Checks scrape job status.

Response:

```json
{
  "job_id": "uuid",
  "status": "completed",
  "asins": ["B000BD0RT0"],
  "result": {
    "B000BD0RT0": {
      "product_saved": true,
      "reviews_saved": 100
    }
  },
  "error": null
}
```

## Architecture

```text
Amazon ASINs
   |
   v
Bright Data scraper API / Playwright
   |
   v
SQLite: products, reviews, images, qna
   |
   +--> Revenue estimator
   |       products.estimated_revenue_per_month
   |
   +--> Claude review analyzer
   |       criteria, product_scores, hooks
   |
   +--> Claude listing generator
           generated_listings
   |
   v
FastAPI dashboard API
   |
   v
React + Tailwind dashboard
```

Core backend modules:

- `backend/scraper.py`: Bright Data product/review scraping
- `backend/revenue_estimator.py`: BSR-based revenue estimates
- `backend/analyzer.py`: Claude-powered review intelligence
- `backend/listing_generator.py`: Claude-powered optimized listing generation
- `backend/api.py`: FastAPI API for the dashboard

Core frontend modules:

- `frontend/src/App.jsx`: four-tab dashboard
- `frontend/src/services/api.js`: frontend API client
- `frontend/src/styles/main.css`: Tailwind entrypoint

## Demo

Local demo:

```text
Frontend: http://127.0.0.1:5173/
Backend:  http://127.0.0.1:8000
```

Deployed demo:

```text
TODO: Add Vercel/Railway URL after deployment.
```

### Demo Dataset (Whey Protein)

For a stable demo run, the dashboard is seeded around this whey competitor set:

- Main ASIN: `B002DYIZHG`
- Competitors: `B099J2SWXV`, `B00XIKPUK4`, `B0CQ32D39X`, `B071JG5QYT`, `B01KITQG0A`, `B09SYB2ZQ2`, `B0BDTMHBC8`, `B07FHPGS4V`
- Amazon URLs: `https://www.amazon.com/dp/B002DYIZHG` and corresponding `/dp/<ASIN>` URLs for each competitor ASIN above.

The successful reference scrape job ID in local SQLite is:

- `24dea35c-027d-4c70-8601-6597db6d97f9`

If a new scrape is slow or fails, click `View existing dashboard` to demo previously stored results.

### Demo Constraints

- Bright Data scrape duration is unpredictable by dataset, ASIN, and queue state. Expect roughly 10 to 30 minutes in some runs.
- To control third-party API spend in this demo, review ingestion is capped at `100 reviews per product`.
- This means the pipeline is architected for scale, but demo runs intentionally trade depth for predictable cost.

## Free Deployment Plan

### Recommended split

1. Frontend on Vercel (Hobby)
2. Backend on Render Free Web Service (FastAPI)

Reason:

- Vercel is excellent for React static/frontend hosting.
- Long-running scrape + analysis jobs are not a good fit for short-lived serverless request execution windows.

### Caveats on free hosting

- Render free services can spin down on idle and cold start on next request.
- Render free instances do not provide production-grade persistence guarantees; SQLite can be reset on restarts/redeploys.
- For durable production data, move from SQLite to managed Postgres.

### Quick deploy sequence

1. Push repo to GitHub.
2. Deploy `frontend` to Vercel. Use `Vite` framework, build command `npm run build --prefix frontend`, output directory `frontend/dist`, and set env `VITE_API_URL=<your-backend-url>`.
3. Deploy backend to Render as a Python Web Service. Use start command `backend/.venv/bin/uvicorn backend.api:app --host 0.0.0.0 --port $PORT` and set env vars `ANTHROPIC_API_KEY`, `CLAUDE_MODEL`, `BRIGHT_DATA_API_KEY`, and Bright Data dataset IDs.
4. Update Vercel `VITE_API_URL` to the Render backend URL.
5. Redeploy frontend.

### Screenshots

Add screenshots after running the local dashboard:

```text
docs/screenshots/competitive-overview.png
docs/screenshots/purchase-criteria.png
docs/screenshots/customer-hooks.png
docs/screenshots/generated-listing.png
```

#### Competitive Overview

![Competitive Overview](docs/screenshots/competitive-overview.png)

#### Purchase Criteria Analysis

![Purchase Criteria Analysis](docs/screenshots/purchase-criteria.png)

#### Customer Hooks Library

![Customer Hooks Library](docs/screenshots/customer-hooks.png)

#### Generated Listing

![Generated Listing](docs/screenshots/generated-listing.png)

## Notes

- Bright Data may return `dead_page` for stale or unavailable ASINs. The scraper records those failures and continues.
- Bright Data review fetches can return late/in-progress responses; retry or reduced ASIN batches may be needed in free/demo budgets.
- The current SQLite database may contain sample/test data from earlier runs. Clear `backend/data.db` if you want a clean dataset.
- If a scrape job fails post-scrape steps, inspect `GET /api/scrape/{job_id}` for stage-level `pipeline` errors.
