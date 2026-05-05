import { BarChart3, Search, Sparkles } from "lucide-react";
import MetricCard from "../components/MetricCard.jsx";

const criteria = [
  { name: "Durability", score: "91%", detail: "Repeatedly mentioned in 4- and 5-star reviews." },
  { name: "Ease of use", score: "84%", detail: "Strong driver for first-time buyers." },
  { name: "Value for money", score: "78%", detail: "Common comparison point against competitors." },
];

const hooks = [
  "Built for everyday use",
  "Simple setup in minutes",
  "Premium feel without the premium hassle",
  "Solves the issue buyers mention most",
];

export default function Dashboard() {
  return (
    <main className="dashboard">
      <header className="topbar">
        <div>
          <p className="eyebrow">Amazon Seller Intelligence</p>
          <h1>Review Analytics Dashboard</h1>
        </div>
        <button className="primary-action" type="button">
          <Search size={18} />
          Analyze ASIN
        </button>
      </header>

      <section className="url-panel">
        <input aria-label="Amazon product URL" placeholder="Paste Amazon product listing URL" />
        <button type="button">Start Analysis</button>
      </section>

      <section className="metrics-grid">
        <MetricCard label="Reviews Analyzed" value="1,248" helper="Target product + 9 competitors" />
        <MetricCard label="Revenue Estimate" value="$84.2k" helper="Monthly competitor average" />
        <MetricCard label="Purchase Criteria" value="12" helper="Ranked by review evidence" />
      </section>

      <section className="content-grid">
        <div className="panel">
          <div className="panel-heading">
            <BarChart3 size={20} />
            <h2>Purchase Criteria</h2>
          </div>
          <div className="criteria-list">
            {criteria.map((item) => (
              <article className="criterion" key={item.name}>
                <div>
                  <strong>{item.name}</strong>
                  <p>{item.detail}</p>
                </div>
                <span>{item.score}</span>
              </article>
            ))}
          </div>
        </div>

        <div className="panel">
          <div className="panel-heading">
            <Sparkles size={20} />
            <h2>Customer Hooks</h2>
          </div>
          <div className="hook-list">
            {hooks.map((hook) => (
              <span key={hook}>{hook}</span>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}
