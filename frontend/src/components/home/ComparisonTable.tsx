const rows = [
  {
    feature: "No sales call required",
    us: { text: "Always — buy instantly online", positive: true },
    them: { text: "Most require a demo or rep", positive: false },
  },
  {
    feature: "Instant CSV download",
    us: { text: "Same-session delivery", positive: true },
    them: { text: "24–48 hr turnaround typical", positive: false },
  },
  {
    feature: "Max resales per lead",
    us: { text: "5 — enforced in database", positive: true },
    them: { text: "Unlimited — rarely disclosed", positive: false },
  },
  {
    feature: "Quality score before buying",
    us: { text: "Transparent 0–100 score shown", positive: true },
    them: { text: "Hidden — you find out after", positive: false },
  },
  {
    feature: "Freshness guarantee",
    us: { text: "180-day cutoff enforced", positive: true },
    them: { text: "Stale data common", positive: false },
  },
  {
    feature: "Bad lead protection",
    us: { text: "Automatic store credit issued", positive: true },
    them: { text: "No recourse offered", positive: false },
  },
  {
    feature: "Free sample before buying",
    us: { text: "5 real leads, no card required", positive: true },
    them: { text: "Pay to see any data", positive: false },
  },
  {
    feature: "No monthly contract",
    us: { text: "Pay per download, cancel anytime", positive: true },
    them: { text: "Monthly commitment usually required", positive: false },
  },
];

export default function ComparisonTable() {
  return (
    <section className="py-20 bg-white">
      <div className="max-w-5xl mx-auto px-6">
        <div className="text-center mb-12">
          <span className="inline-block bg-blue-50 text-blue-600 text-xs font-bold tracking-widest uppercase px-4 py-1.5 rounded-full mb-4">
            Why LeadGen
          </span>
          <h2 className="text-3xl sm:text-4xl font-black text-slate-900 mb-4">
            Built differently from every lead vendor you've tried
          </h2>
          <p className="text-slate-500 text-lg max-w-2xl mx-auto">
            Most lead vendors hide the fine print. We put it on the homepage.
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200 overflow-hidden shadow-sm">
          {/* Header */}
          <div className="grid grid-cols-3 bg-slate-900 text-white text-sm font-semibold">
            <div className="px-6 py-4 text-slate-400">Feature</div>
            <div className="px-6 py-4 text-blue-300 border-l border-slate-700">LeadGen</div>
            <div className="px-6 py-4 text-slate-400 border-l border-slate-700">Typical Competitors</div>
          </div>

          {/* Rows */}
          {rows.map((row, i) => (
            <div
              key={row.feature}
              className={`grid grid-cols-3 text-sm border-t border-slate-100 ${i % 2 === 0 ? "bg-white" : "bg-slate-50"}`}
            >
              <div className="px-6 py-4 font-medium text-slate-700 flex items-center">
                {row.feature}
              </div>
              <div className="px-6 py-4 border-l border-slate-100 flex items-center gap-2">
                <span className="w-5 h-5 bg-emerald-100 rounded-full flex items-center justify-center shrink-0">
                  <svg className="w-3 h-3 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                  </svg>
                </span>
                <span className="text-slate-700">{row.us.text}</span>
              </div>
              <div className="px-6 py-4 border-l border-slate-100 flex items-center gap-2">
                <span className="w-5 h-5 bg-red-100 rounded-full flex items-center justify-center shrink-0">
                  <svg className="w-3 h-3 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </span>
                <span className="text-slate-500">{row.them.text}</span>
              </div>
            </div>
          ))}
        </div>

        <p className="text-center text-xs text-slate-400 mt-4">
          Based on public pricing pages and terms of major B2B lead vendors as of 2025.
        </p>
      </div>
    </section>
  );
}
