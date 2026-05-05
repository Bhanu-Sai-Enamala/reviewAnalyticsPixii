const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function request(path, options = {}) {
  const response = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers ?? {}) },
    ...options,
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }

  return response.json();
}

export function getProducts() {
  return request("/api/products");
}

export function getCriteria() {
  return request("/api/criteria");
}

export function getHooks({ sentiment, minFrequency } = {}) {
  const params = new URLSearchParams();
  if (sentiment && sentiment !== "all") params.set("sentiment", sentiment);
  if (minFrequency) params.set("min_frequency", String(minFrequency));
  const query = params.toString();
  return request(`/api/hooks${query ? `?${query}` : ""}`);
}

export function getListing(asin) {
  return request(`/api/listing/${asin}`);
}

export function startScrape(asins) {
  return request("/api/scrape", {
    method: "POST",
    body: JSON.stringify({ asins }),
  });
}

export function getScrapeJob(jobId) {
  return request(`/api/scrape/${jobId}`);
}

export function startScrapeFromUrls({ productUrl, competitorUrls }) {
  return request("/api/scrape-urls", {
    method: "POST",
    body: JSON.stringify({ product_url: productUrl, competitor_urls: competitorUrls }),
  });
}

export async function analyzeListing(payload) {
  return request("/api/analyze", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
