import React, { useEffect, useMemo, useState } from "react";
import {
  BarChart3,
  Check,
  Clipboard,
  Copy,
  FileText,
  LayoutDashboard,
  Search,
  SlidersHorizontal,
  Sparkles,
  Trophy,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  getCriteria,
  getHooks,
  getListing,
  getProducts,
  getScrapeJob,
  startScrapeFromUrls,
} from "./services/api.js";

const MAIN_ASIN = "B07JZHXXBT";

const products = [
  {
    asin: "B07JZHXXBT",
    product: "Magnesium Supplement Main Product",
    price: null,
    rating: null,
    reviews: null,
    revenue: null,
    bsr: null,
    status: "Needs fresh scrape",
  },
  {
    asin: "B000BD0RT0",
    product: "Doctor's Best High Absorption Magnesium Glycinate Lysinate",
    price: 20.99,
    rating: 4.6,
    reviews: 75298,
    revenue: 167920,
    bsr: 7,
    status: "Scraped",
  },
  {
    asin: "B07FK237C5",
    product: "Competitor Magnesium ASIN B07FK237C5",
    price: null,
    rating: null,
    reviews: null,
    revenue: null,
    bsr: null,
    status: "Dead page",
  },
  {
    asin: "B07QCY5ZYH",
    product: "Competitor Magnesium ASIN B07QCY5ZYH",
    price: null,
    rating: null,
    reviews: null,
    revenue: null,
    bsr: null,
    status: "Dead page",
  },
  {
    asin: "B07FK28Z98",
    product: "Competitor Magnesium ASIN B07FK28Z98",
    price: null,
    rating: null,
    reviews: null,
    revenue: null,
    bsr: null,
    status: "Dead page",
  },
  {
    asin: "B07TWKR3X1",
    product: "Competitor Magnesium ASIN B07TWKR3X1",
    price: null,
    rating: null,
    reviews: null,
    revenue: null,
    bsr: null,
    status: "Dead page",
  },
  {
    asin: "B01HCVVX76",
    product: "Competitor Magnesium ASIN B01HCVVX76",
    price: null,
    rating: null,
    reviews: null,
    revenue: null,
    bsr: null,
    status: "Dead page",
  },
  {
    asin: "B07FK25HFB",
    product: "Competitor Magnesium ASIN B07FK25HFB",
    price: null,
    rating: null,
    reviews: null,
    revenue: null,
    bsr: null,
    status: "Dead page",
  },
  {
    asin: "B07FKCKQ9P",
    product: "Competitor Magnesium ASIN B07FKCKQ9P",
    price: null,
    rating: null,
    reviews: null,
    revenue: null,
    bsr: null,
    status: "Dead page",
  },
  {
    asin: "B07FK3GJ8Q",
    product: "Competitor Magnesium ASIN B07FK3GJ8Q",
    price: null,
    rating: null,
    reviews: null,
    revenue: null,
    bsr: null,
    status: "Dead page",
  },
];

const criteria = [
  {
    id: "effectiveness",
    name: "Effectiveness",
    description: "Customers evaluate whether the supplement delivers better sleep, relaxation, and muscle support.",
    mentionCount: 40,
    scores: [
      { asin: "B07JZHXXBT", product: "Your product", score: 0 },
      { asin: "B000BD0RT0", product: "Doctor's Best", score: 8 },
    ],
  },
  {
    id: "pill_size_swallowability",
    name: "Pill size / swallowability",
    description: "Customers repeatedly mention whether tablets are large, chalky, or hard to swallow.",
    mentionCount: 40,
    scores: [
      { asin: "B07JZHXXBT", product: "Your product", score: 0 },
      { asin: "B000BD0RT0", product: "Doctor's Best", score: 3 },
    ],
  },
  {
    id: "stomach_tolerance",
    name: "Stomach tolerance",
    description: "Buyers want a magnesium form that is gentle and does not cause digestive discomfort.",
    mentionCount: 20,
    scores: [
      { asin: "B07JZHXXBT", product: "Your product", score: 0 },
      { asin: "B000BD0RT0", product: "Doctor's Best", score: 7.5 },
    ],
  },
  {
    id: "anxiety_muscle_relief",
    name: "Anxiety / muscle relief",
    description: "Customers value calm, cramp support, reduced tension, and nighttime relaxation.",
    mentionCount: 18,
    scores: [
      { asin: "B07JZHXXBT", product: "Your product", score: 0 },
      { asin: "B000BD0RT0", product: "Doctor's Best", score: 8 },
    ],
  },
  {
    id: "value_for_money",
    name: "Value for money",
    description: "Customers compare price, tablet count, perceived quality, and repeat-purchase value.",
    mentionCount: 14,
    scores: [
      { asin: "B07JZHXXBT", product: "Your product", score: 0 },
      { asin: "B000BD0RT0", product: "Doctor's Best", score: 8 },
    ],
  },
];

const hooks = [
  { phrase: "sleep better", sentiment: "positive", frequency: 17, asins: ["B000BD0RT0"] },
  { phrase: "hard to swallow", sentiment: "negative", frequency: 17, asins: ["B000BD0RT0"] },
  { phrase: "pills are huge", sentiment: "negative", frequency: 12, asins: ["B000BD0RT0"] },
  { phrase: "anxiety relief", sentiment: "positive", frequency: 11, asins: ["B000BD0RT0"] },
  { phrase: "works amazing", sentiment: "positive", frequency: 8, asins: ["B000BD0RT0"] },
  { phrase: "too large", sentiment: "negative", frequency: 8, asins: ["B000BD0RT0"] },
  { phrase: "gentle on stomach", sentiment: "positive", frequency: 7, asins: ["B000BD0RT0"] },
  { phrase: "great value", sentiment: "positive", frequency: 7, asins: ["B000BD0RT0"] },
  { phrase: "calm relaxation", sentiment: "positive", frequency: 6, asins: ["B000BD0RT0"] },
  { phrase: "stomach friendly", sentiment: "positive", frequency: 5, asins: ["B000BD0RT0"] },
];

const currentListing = {
  title: "Magnesium Supplement Main Product",
  bullets: [
    "Supports wellness with magnesium.",
    "Designed for daily supplementation.",
    "Made for adults seeking mineral support.",
    "Convenient bottle for home use.",
    "Follow label directions for best results.",
  ],
  description:
    "Current listing content is sparse. The review analysis suggests the page should more clearly address sleep, stomach tolerance, relaxation, swallowability, and value.",
};

const generatedListing = {
  title:
    "High Absorption Magnesium Glycinate for Sleep Better, Calm Relaxation & Gentle Stomach Support - Easy Daily Magnesium Supplement",
  bullets: [
    "Sleep better with high absorption magnesium designed to support calm nights and everyday relaxation.",
    "Gentle on stomach formula helps avoid digestive discomfort while supporting daily mineral needs.",
    "Positioned against huge, hard-to-swallow pills with customer-first comfort and usability claims.",
    "Uses customer language like anxiety relief, works amazing, and great value to reinforce trust.",
    "Daily reassurance: clear dosage, dependable quality, and support for repeat wellness routines.",
  ],
  description:
    "Restless nights, muscle tension, and daily stress can make it hard to feel your best. This optimized magnesium listing positions the product around the outcomes shoppers repeatedly ask for: sleep better, calm relaxation, and dependable support without unnecessary friction.\n\nCustomers care most about effectiveness, pill size, stomach tolerance, anxiety and muscle relief, and value for money. The new copy brings those criteria forward with natural language that mirrors real review hooks, including gentle on stomach, anxiety relief, works amazing, and great value.\n\nChoose a magnesium supplement that makes the buying decision easier. With a clearer benefit promise, stronger reassurance, and customer-led phrasing, this listing is built to answer objections quickly and help shoppers feel confident adding it to their daily routine.",
};

const emptyGeneratedListing = {
  title: "",
  bullets: [],
  description: "",
};

const tabs = [
  { id: "overview", label: "Competitive Overview", icon: LayoutDashboard },
  { id: "criteria", label: "Purchase Criteria", icon: BarChart3 },
  { id: "hooks", label: "Customer Hooks", icon: Clipboard },
  { id: "listing", label: "Generated Listing", icon: FileText },
];

const formatCurrency = (value) => (value == null ? "—" : `$${value.toLocaleString()}`);
const formatNumber = (value) => (value == null ? "—" : value.toLocaleString());
const formatValue = (value) => (value == null ? "—" : value);

function classNames(...items) {
  return items.filter(Boolean).join(" ");
}

function compactProductLabel(text, asin, max = 24) {
  const base = (text || asin || "Product").trim();
  if (base.length <= max) return base;
  const short = base.slice(0, Math.max(8, max - 1)).trimEnd();
  return `${short}…`;
}

function compactAsinLabel(asin, isMain = false) {
  return isMain ? `${asin} (You)` : asin;
}

function sentimentClasses(sentiment) {
  if (sentiment === "positive") return "bg-emerald-50 text-emerald-700 ring-emerald-200";
  if (sentiment === "negative") return "bg-rose-50 text-rose-700 ring-rose-200";
  return "bg-amber-50 text-amber-700 ring-amber-200";
}

function App() {
  const [showDashboard, setShowDashboard] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [scrapeJob, setScrapeJob] = useState(null);
  const [activeTab, setActiveTab] = useState("overview");
  const [sort, setSort] = useState({ key: "revenue", direction: "desc" });
  const [selectedAsin, setSelectedAsin] = useState("B000BD0RT0");
  const [hookQuery, setHookQuery] = useState("");
  const [sentimentFilter, setSentimentFilter] = useState("all");
  const [copied, setCopied] = useState("");
  const [productsData, setProductsData] = useState([]);
  const [criteriaData, setCriteriaData] = useState([]);
  const [hooksData, setHooksData] = useState([]);
  const [listingData, setListingData] = useState({ current: currentListing, generated: emptyGeneratedListing });
  const [loading, setLoading] = useState(true);
  const [apiError, setApiError] = useState("");

  useEffect(() => {
    if (!showDashboard) return undefined;
    let cancelled = false;

    async function loadDashboard() {
      setLoading(true);
      setApiError("");
      try {
        const [productsResponse, criteriaResponse, hooksResponse] = await Promise.all([
          getProducts(),
          getCriteria(),
          getHooks(),
        ]);

        if (cancelled) return;
        setProductsData(productsResponse);
        setCriteriaData(criteriaResponse);
        setHooksData(hooksResponse);

        const preferredAsin =
          productsResponse.find((product) => product.title)?.asin ?? productsResponse[0]?.asin ?? selectedAsin;
        setSelectedAsin(preferredAsin);
      } catch (error) {
        if (!cancelled) {
          setApiError(error.message);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadDashboard();
    return () => {
      cancelled = true;
    };
  }, [showDashboard, refreshKey]);

  useEffect(() => {
    if (!scrapeJob?.job_id || ["completed", "completed_with_errors", "failed"].includes(scrapeJob.status)) return undefined;

    let cancelled = false;
    const timer = window.setInterval(async () => {
      try {
        const nextJob = await getScrapeJob(scrapeJob.job_id);
        if (cancelled) return;
        setScrapeJob(nextJob);
        if (["completed", "completed_with_errors"].includes(nextJob.status)) {
          setShowDashboard(true);
          setActiveTab("overview");
          setRefreshKey((value) => value + 1);
          window.clearInterval(timer);
        }
        if (nextJob.status === "failed") {
          window.clearInterval(timer);
        }
      } catch (error) {
        if (!cancelled) setScrapeJob((job) => ({ ...job, status: "failed", error: error.message }));
        window.clearInterval(timer);
      }
    }, 3500);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [scrapeJob?.job_id, scrapeJob?.status]);

  useEffect(() => {
    let cancelled = false;

    async function loadListing() {
      try {
        const listingResponse = await getListing(selectedAsin);
        if (cancelled) return;
        setListingData({
          current: normalizeListing(listingResponse.current, currentListing),
          generated: normalizeListing(listingResponse.generated, emptyGeneratedListing),
        });
      } catch {
        if (!cancelled) {
          setListingData({
            current: { ...currentListing, title: selectedAsin ? `ASIN ${selectedAsin}` : currentListing.title },
            generated: emptyGeneratedListing,
          });
        }
      }
    }

    if (selectedAsin) loadListing();
    return () => {
      cancelled = true;
    };
  }, [selectedAsin]);

  const sortedProducts = useMemo(() => {
    return [...productsData].sort((a, b) => {
      const direction = sort.direction === "asc" ? 1 : -1;
      const av = a[sort.key];
      const bv = b[sort.key];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      if (typeof av === "string") return av.localeCompare(bv) * direction;
      return (av - bv) * direction;
    });
  }, [productsData, sort]);

  const filteredHooks = useMemo(() => {
    return hooksData
      .filter((hook) => hook.phrase.toLowerCase().includes(hookQuery.toLowerCase()))
      .filter((hook) => sentimentFilter === "all" || hook.sentiment === sentimentFilter)
      .sort((a, b) => b.frequency - a.frequency);
  }, [hooksData, hookQuery, sentimentFilter]);

  const selectedProduct = productsData.find((product) => product.asin === selectedAsin) ?? productsData[0] ?? {
    asin: selectedAsin || "—",
    product: selectedAsin ? `ASIN ${selectedAsin}` : "No product selected",
    price: null,
    rating: null,
    reviews: null,
    revenue: null,
    bsr: null,
  };

  const copyText = async (text, label) => {
    await navigator.clipboard.writeText(text);
    setCopied(label);
    window.setTimeout(() => setCopied(""), 1400);
  };

  const startUrlScrape = async ({ productUrl, competitorUrls }) => {
    const job = await startScrapeFromUrls({ productUrl, competitorUrls });
    setScrapeJob(job);
  };

  if (!showDashboard) {
    return (
      <SetupScreen
        scrapeJob={scrapeJob}
        onStart={startUrlScrape}
        onViewDashboard={() => setShowDashboard(true)}
      />
    );
  }

  return (
    <main className="min-h-screen bg-[#f5f7f8] text-ink">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-5 py-6 lg:px-8">
        <header className="flex flex-col gap-4 border-b border-slate-200 pb-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="mb-2 text-xs font-bold uppercase text-teal-700">Amazon Seller Intelligence</p>
            <h1 className="text-3xl font-bold tracking-normal text-ink lg:text-4xl">Review Analytics Dashboard</h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-muted">
              Compare competitors, inspect purchase criteria, collect customer language, and turn the analysis into optimized listing copy.
            </p>
          </div>
          <div className="grid grid-cols-3 gap-3 text-sm">
            <Metric label="Products" value={productsData.length} />
            <Metric label="Scraped" value={productsData.filter((product) => product.title).length} />
            <Metric label="Hooks" value={hooksData.length} />
          </div>
        </header>

        {(loading || apiError) && (
          <div className={classNames(
            "rounded-lg border px-4 py-3 text-sm",
            apiError ? "border-amber-200 bg-amber-50 text-amber-900" : "border-teal-200 bg-teal-50 text-teal-900",
          )}>
            {loading ? "Loading live dashboard data from FastAPI..." : `Could not load live dashboard data: ${apiError}`}
          </div>
        )}

        <nav className="grid gap-2 rounded-lg border border-slate-200 bg-white p-2 shadow-sm md:grid-cols-4">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                className={classNames(
                  "flex min-h-11 items-center justify-center gap-2 rounded-md px-3 text-sm font-semibold transition",
                  activeTab === tab.id
                    ? "bg-teal-700 text-white shadow-sm"
                    : "text-slate-600 hover:bg-slate-50 hover:text-ink",
                )}
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                type="button"
              >
                <Icon size={17} />
                {tab.label}
              </button>
            );
          })}
        </nav>

        {activeTab === "overview" && (
          <OverviewTab
            onSelect={setSelectedAsin}
            products={sortedProducts}
            selectedAsin={selectedAsin}
            selectedProduct={selectedProduct}
            setSort={setSort}
            sort={sort}
          />
        )}

        {activeTab === "criteria" && <CriteriaTab criteria={criteriaData} />}

        {activeTab === "hooks" && (
          <HooksTab
            copied={copied}
            copyText={copyText}
            filteredHooks={filteredHooks}
            hookQuery={hookQuery}
            sentimentFilter={sentimentFilter}
            setHookQuery={setHookQuery}
            setSentimentFilter={setSentimentFilter}
          />
        )}

        {activeTab === "listing" && <ListingTab copied={copied} copyText={copyText} listingData={listingData} />}
      </div>
    </main>
  );
}

function normalizeListing(listing, fallback) {
  if (!listing) return fallback;
  return {
    title: listing.title || fallback.title,
    bullets: Array.isArray(listing.bullets) ? listing.bullets : fallback.bullets,
    description: listing.description || fallback.description,
  };
}

function SetupScreen({ scrapeJob, onStart, onViewDashboard }) {
  const [productUrl, setProductUrl] = useState("");
  const [competitorText, setCompetitorText] = useState("");
  const [formError, setFormError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const competitorUrls = competitorText
    .split(/\n|,/)
    .map((value) => value.trim())
    .filter(Boolean)
    .slice(0, 9);

  const submit = async (event) => {
    event.preventDefault();
    setFormError("");
    if (!productUrl.trim()) {
      setFormError("Paste your Amazon listing URL first.");
      return;
    }

    setSubmitting(true);
    try {
      await onStart({ productUrl: productUrl.trim(), competitorUrls });
    } catch (error) {
      setFormError(error.message);
    } finally {
      setSubmitting(false);
    }
  };

  const running = scrapeJob && !["completed", "completed_with_errors", "failed"].includes(scrapeJob.status);

  return (
    <main className="min-h-screen bg-[#f5f7f8] px-5 py-8 text-ink">
      <div className="mx-auto grid w-full max-w-6xl gap-6 lg:grid-cols-[1fr_420px]">
        <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-panel">
          <p className="mb-2 text-xs font-bold uppercase text-teal-700">Review Analytics Engine</p>
          <h1 className="text-3xl font-bold lg:text-4xl">Start with your Amazon listing URL</h1>
          <p className="mt-4 max-w-2xl text-sm leading-6 text-muted">
            Paste your product URL and add up to 9 competitor URLs. The backend will extract ASINs, scrape listings
            and reviews, estimate revenue, then refresh the dashboard with the scraped data.
          </p>

          <form className="mt-8 grid gap-5" onSubmit={submit}>
            <label className="grid gap-2">
              <span className="text-sm font-bold">Your Amazon product URL</span>
              <input
                className="h-12 rounded-md border border-slate-200 px-4 outline-none ring-teal-600 transition focus:ring-2"
                onChange={(event) => setProductUrl(event.target.value)}
                placeholder="https://www.amazon.com/dp/B000BD0RT0"
                value={productUrl}
              />
            </label>

            <label className="grid gap-2">
              <span className="text-sm font-bold">Competitor URLs</span>
              <textarea
                className="min-h-40 rounded-md border border-slate-200 p-4 outline-none ring-teal-600 transition focus:ring-2"
                onChange={(event) => setCompetitorText(event.target.value)}
                placeholder={"Paste up to 9 competitor URLs, one per line\nhttps://www.amazon.com/dp/...\nhttps://www.amazon.com/dp/..."}
                value={competitorText}
              />
              <span className="text-xs text-muted">{competitorUrls.length}/9 competitor URLs ready</span>
            </label>

            {formError && (
              <div className="rounded-md border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
                {formError}
              </div>
            )}

            {scrapeJob && (
              <div className="rounded-md border border-teal-200 bg-teal-50 px-4 py-3 text-sm text-teal-900">
                <p className="font-bold">Scrape job: {scrapeJob.status}</p>
                <p className="mt-1 break-all text-xs">Job ID: {scrapeJob.job_id}</p>
                {scrapeJob.error && <p className="mt-2 text-rose-700">{scrapeJob.error}</p>}
              </div>
            )}

            <div className="flex flex-col gap-3 sm:flex-row">
              <button
                className="inline-flex h-12 items-center justify-center gap-2 rounded-md bg-teal-700 px-5 text-sm font-bold text-white transition hover:bg-teal-800 disabled:cursor-not-allowed disabled:opacity-60"
                disabled={submitting || running}
                type="submit"
              >
                <Sparkles size={18} />
                {running ? "Scraping..." : "Scrape URLs"}
              </button>
              <button
                className="inline-flex h-12 items-center justify-center rounded-md border border-slate-200 px-5 text-sm font-bold text-slate-700 transition hover:bg-slate-50"
                onClick={onViewDashboard}
                type="button"
              >
                View existing dashboard
              </button>
            </div>
          </form>
        </section>

        <aside className="rounded-lg border border-slate-200 bg-white p-6 shadow-panel">
          <h2 className="text-lg font-bold">Simple workflow</h2>
          <div className="mt-5 grid gap-3 text-sm">
            {[
              ["1", "Paste your listing URL"],
              ["2", "Paste 9 or fewer competitor URLs"],
              ["3", "Scrape product listings and reviews"],
              ["4", "Estimate monthly revenue from BSR"],
              ["5", "Review the dashboard"],
            ].map(([step, label]) => (
              <div className="flex gap-3 rounded-md bg-slate-50 p-3" key={step}>
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-teal-700 text-xs font-bold text-white">
                  {step}
                </span>
                <p className="font-medium">{label}</p>
              </div>
            ))}
          </div>
          <p className="mt-5 text-xs leading-5 text-muted">
            Bright Data may reject stale ASINs as dead pages. Use fresh live Amazon URLs from search results for the best success rate.
          </p>
        </aside>
      </div>
    </main>
  );
}

function Metric({ label, value }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-4 py-3 shadow-sm">
      <p className="text-xs font-medium text-muted">{label}</p>
      <p className="mt-1 text-xl font-bold text-ink">{value}</p>
    </div>
  );
}

function SortButton({ column, label, sort, setSort }) {
  const active = sort.key === column;
  return (
    <button
      className="inline-flex items-center gap-1 font-semibold text-slate-600 hover:text-ink"
      onClick={() =>
        setSort((current) => ({
          key: column,
          direction: current.key === column && current.direction === "desc" ? "asc" : "desc",
        }))
      }
      type="button"
    >
      {label}
      <SlidersHorizontal className={active ? "text-teal-700" : "text-slate-300"} size={14} />
    </button>
  );
}

function OverviewTab({ products, selectedProduct, selectedAsin, onSelect, sort, setSort }) {
  return (
    <section className="grid gap-5 lg:grid-cols-[1fr_340px]">
      <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-panel">
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <div>
            <h2 className="text-lg font-bold">Competitive Overview</h2>
            <p className="text-sm text-muted">Sortable product metrics from Bright Data and revenue estimates.</p>
          </div>
          <Trophy className="text-teal-700" size={22} />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[880px] text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">
                  <SortButton column="product" label="Product" setSort={setSort} sort={sort} />
                </th>
                <th className="px-4 py-3">
                  <SortButton column="price" label="Price" setSort={setSort} sort={sort} />
                </th>
                <th className="px-4 py-3">
                  <SortButton column="rating" label="Rating" setSort={setSort} sort={sort} />
                </th>
                <th className="px-4 py-3">
                  <SortButton column="reviews" label="Reviews" setSort={setSort} sort={sort} />
                </th>
                <th className="px-4 py-3">
                  <SortButton column="revenue" label="Est. Revenue/Mo" setSort={setSort} sort={sort} />
                </th>
                <th className="px-4 py-3">
                  <SortButton column="bsr" label="BSR" setSort={setSort} sort={sort} />
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {products.map((product) => (
                <tr
                  className={classNames(
                    "cursor-pointer transition hover:bg-teal-50/60",
                    product.asin === MAIN_ASIN && "bg-amber-50",
                    product.asin === selectedAsin && "outline outline-2 outline-inset outline-teal-500",
                  )}
                  key={product.asin}
                  onClick={() => onSelect(product.asin)}
                >
                  <td className="px-4 py-4">
                    <div className="max-w-md">
                      <div className="flex items-center gap-2">
                        <p className="font-semibold text-ink">{product.product}</p>
                        {product.asin === MAIN_ASIN && (
                          <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-bold text-amber-800">
                            Main
                          </span>
                        )}
                      </div>
                      <p className="mt-1 text-xs text-muted">{product.asin} · {product.status}</p>
                    </div>
                  </td>
                  <td className="px-4 py-4 font-medium">{formatCurrency(product.price)}</td>
                  <td className="px-4 py-4">{formatValue(product.rating)}</td>
                  <td className="px-4 py-4">{formatNumber(product.reviews)}</td>
                  <td className="px-4 py-4 font-semibold text-teal-700">{formatCurrency(product.revenue)}</td>
                  <td className="px-4 py-4">{formatNumber(product.bsr)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <aside className="rounded-lg border border-slate-200 bg-white p-5 shadow-panel">
        <p className="text-xs font-bold uppercase text-teal-700">Selected product</p>
        <h3 className="mt-2 text-xl font-bold">{selectedProduct.product}</h3>
        <dl className="mt-5 grid gap-3 text-sm">
          <Detail label="ASIN" value={selectedProduct.asin} />
          <Detail label="Price" value={formatCurrency(selectedProduct.price)} />
          <Detail label="Rating" value={formatValue(selectedProduct.rating)} />
          <Detail label="Reviews" value={formatNumber(selectedProduct.reviews)} />
          <Detail label="Est. Revenue/Mo" value={formatCurrency(selectedProduct.revenue)} />
          <Detail label="BSR" value={formatNumber(selectedProduct.bsr)} />
        </dl>
      </aside>
    </section>
  );
}

function Detail({ label, value }) {
  return (
    <div className="flex items-center justify-between rounded-md bg-slate-50 px-3 py-2">
      <dt className="text-muted">{label}</dt>
      <dd className="font-semibold">{value}</dd>
    </div>
  );
}

function CriteriaTab({ criteria }) {
  if (!criteria.length) {
    return (
      <EmptyState
        icon={BarChart3}
        title="No purchase criteria for this scrape yet"
        message="The scraped product table is live, but review analysis has not been generated for this current ASIN set."
      />
    );
  }

  return (
    <section className="grid gap-4">
      {criteria.map((criterion) => {
        const chartData = (criterion.scores || []).map((entry) => ({
          ...entry,
          label: compactAsinLabel(entry.asin, entry.is_main),
          fullLabel: entry.product || entry.asin,
        }));

        return (
        <article className="rounded-lg border border-slate-200 bg-white p-5 shadow-panel" key={criterion.id}>
          <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold">{criterion.name}</h2>
                <span className="rounded-full bg-teal-50 px-2 py-1 text-xs font-bold text-teal-700">
                  {criterion.mentionCount} mentions
                </span>
              </div>
              <p className="mt-3 text-sm leading-6 text-muted">{criterion.description}</p>
            </div>
            <div className="h-52">
              <ResponsiveContainer height="100%" width="100%">
                <BarChart data={chartData} layout="vertical" margin={{ left: 20, right: 20 }}>
                  <CartesianGrid horizontal={false} stroke="#E2E8F0" />
                  <XAxis domain={[0, 10]} type="number" />
                  <YAxis dataKey="label" type="category" width={125} />
                  <Tooltip
                    formatter={(value) => [value, "Score"]}
                    labelFormatter={(_, payload) => {
                      const row = payload?.[0]?.payload;
                      return row ? `${row.fullLabel} (${row.asin})` : "";
                    }}
                  />
                  <Bar dataKey="score" radius={[0, 6, 6, 0]}>
                    {chartData.map((entry) => (
                      <Cell fill={entry.asin === MAIN_ASIN ? "#F59E0B" : "#0F766E"} key={entry.asin} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </article>
      )})}
    </section>
  );
}

function HooksTab({
  copied,
  copyText,
  filteredHooks,
  hookQuery,
  sentimentFilter,
  setHookQuery,
  setSentimentFilter,
}) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white shadow-panel">
      <div className="grid gap-3 border-b border-slate-200 p-5 md:grid-cols-[1fr_220px]">
        <label className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
          <input
            className="h-11 w-full rounded-md border border-slate-200 pl-10 pr-3 outline-none ring-teal-600 transition focus:ring-2"
            onChange={(event) => setHookQuery(event.target.value)}
            placeholder="Search customer phrases"
            value={hookQuery}
          />
        </label>
        <select
          className="h-11 rounded-md border border-slate-200 px-3 outline-none ring-teal-600 transition focus:ring-2"
          onChange={(event) => setSentimentFilter(event.target.value)}
          value={sentimentFilter}
        >
          <option value="all">All sentiments</option>
          <option value="positive">Positive</option>
          <option value="neutral">Neutral</option>
          <option value="negative">Negative</option>
        </select>
      </div>
      <div className="divide-y divide-slate-100">
        {filteredHooks.length ? (
          filteredHooks.map((hook) => (
            <article className="grid gap-3 px-5 py-4 md:grid-cols-[1fr_auto_auto_auto]" key={hook.phrase}>
              <div>
                <p className="font-semibold">“{hook.phrase}”</p>
                <p className="mt-1 text-xs text-muted">{hook.asins.join(", ")}</p>
              </div>
              <span className={classNames("w-fit rounded-full px-2.5 py-1 text-xs font-bold ring-1", sentimentClasses(hook.sentiment))}>
                {hook.sentiment}
              </span>
              <span className="w-fit rounded-md bg-slate-50 px-3 py-1 text-sm font-bold text-ink">
                {hook.frequency}x
              </span>
              <button
                className="inline-flex h-9 items-center justify-center gap-2 rounded-md border border-slate-200 px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
                onClick={() => copyText(hook.phrase, hook.phrase)}
                type="button"
              >
                {copied === hook.phrase ? <Check size={16} /> : <Copy size={16} />}
                Copy
              </button>
            </article>
          ))
        ) : (
          <div className="px-5 py-10">
            <EmptyState
              icon={Clipboard}
              title="No customer hooks for this scrape yet"
              message="Run the review analyzer after scraping to mine repeated customer phrases for these ASINs."
              compact
            />
          </div>
        )}
      </div>
    </section>
  );
}

function ListingTab({ copied, copyText, listingData }) {
  const current = listingData?.current ?? currentListing;
  const generated = listingData?.generated ?? emptyGeneratedListing;
  const hasGeneratedListing = Boolean(generated.title || generated.bullets.length || generated.description);
  const liveListingText = `${generated.title}\n\n${generated.bullets.map((bullet) => `• ${bullet}`).join("\n")}\n\n${generated.description}`;

  return (
    <section className="grid gap-5 lg:grid-cols-2">
      <ListingPanel listing={current} title="Current Listing" tone="current" />
      <div className="rounded-lg border border-teal-200 bg-white shadow-panel">
        <div className="flex items-center justify-between border-b border-teal-100 px-5 py-4">
          <div className="flex items-center gap-2">
            <Sparkles className="text-teal-700" size={20} />
            <h2 className="text-lg font-bold">AI-Generated Listing</h2>
          </div>
          <button
            className="inline-flex h-10 items-center gap-2 rounded-md bg-teal-700 px-4 text-sm font-bold text-white transition hover:bg-teal-800 disabled:cursor-not-allowed disabled:bg-slate-300"
            disabled={!hasGeneratedListing}
            onClick={() => copyText(liveListingText, "listing")}
            type="button"
          >
            {copied === "listing" ? <Check size={16} /> : <Copy size={16} />}
            Copy new listing
          </button>
        </div>
        {hasGeneratedListing ? (
          <ListingBody listing={generated} highlight />
        ) : (
          <div className="p-5">
            <EmptyState
              icon={Sparkles}
              title="No generated listing for this product yet"
              message="After review analysis is available, run the listing generator for the selected ASIN to create optimized copy."
              compact
            />
          </div>
        )}
      </div>
    </section>
  );
}

function ListingPanel({ listing, title }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white shadow-panel">
      <div className="border-b border-slate-200 px-5 py-4">
        <h2 className="text-lg font-bold">{title}</h2>
      </div>
      <ListingBody listing={listing} />
    </div>
  );
}

function ListingBody({ listing, highlight = false }) {
  return (
    <div className="grid gap-5 p-5">
      <section>
        <p className="mb-2 text-xs font-bold uppercase text-muted">Title</p>
        <p className={classNames("rounded-md p-3 text-sm font-semibold leading-6", highlight ? "bg-emerald-50 text-emerald-950" : "bg-slate-50")}>
          {listing.title}
        </p>
      </section>
      <section>
        <p className="mb-2 text-xs font-bold uppercase text-muted">Bullets</p>
        <ul className="grid gap-2">
          {listing.bullets.map((bullet) => (
            <li className={classNames("rounded-md p-3 text-sm leading-6", highlight ? "bg-teal-50" : "bg-slate-50")} key={bullet}>
              {highlight && <span className="mr-2 font-bold text-teal-700">New</span>}
              {bullet}
            </li>
          ))}
        </ul>
      </section>
      <section>
        <p className="mb-2 text-xs font-bold uppercase text-muted">Description</p>
        <div className={classNames("whitespace-pre-line rounded-md p-3 text-sm leading-6", highlight ? "bg-emerald-50" : "bg-slate-50")}>
          {listing.description}
        </div>
      </section>
    </div>
  );
}

function EmptyState({ icon: Icon, title, message, compact = false }) {
  return (
    <div className={classNames(
      "flex flex-col items-center justify-center rounded-lg border border-dashed border-slate-200 bg-white text-center",
      compact ? "px-5 py-8" : "min-h-80 px-6 py-12 shadow-panel",
    )}>
      <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-full bg-teal-50 text-teal-700">
        <Icon size={20} />
      </div>
      <h2 className="text-lg font-bold text-ink">{title}</h2>
      <p className="mt-2 max-w-xl text-sm leading-6 text-muted">{message}</p>
    </div>
  );
}

export default App;
