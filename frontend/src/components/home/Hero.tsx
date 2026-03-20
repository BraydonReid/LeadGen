import Link from "next/link";

export default function Hero({ totalLeads, consumerIntentCount }: { totalLeads: number; consumerIntentCount?: number }) {
  const formatted = totalLeads > 0 ? totalLeads.toLocaleString() : "500,000+";
  const intentFormatted = consumerIntentCount && consumerIntentCount > 0 ? consumerIntentCount.toLocaleString() : "500+";

  return (
    <section className="bg-gradient-to-br from-slate-900 via-slate-800 to-blue-900 text-white">
      <div className="max-w-6xl mx-auto px-6 py-24 lg:py-32">
        <div className="max-w-3xl">
          <div className="inline-flex items-center gap-2 bg-blue-500/20 border border-blue-400/30 rounded-full px-4 py-1.5 text-sm text-blue-300 mb-8">
            <span className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
            Texas-focused contractor &amp; business leads
          </div>

          <h1 className="text-5xl lg:text-6xl font-extrabold leading-tight mb-6">
            Texas Business Leads.
            <br />
            <span className="text-blue-400">No Sales Rep Required.</span>
          </h1>

          <p className="text-lg lg:text-xl text-slate-300 mb-10 leading-relaxed">
            Browse <strong className="text-white">{formatted} verified Texas contacts</strong> —
            business directories and{" "}
            <span className="text-teal-400 font-semibold">consumer intent leads</span> from Texas homeowners
            actively seeking contractors. Filter by city, pick your quantity, and download your CSV instantly.
            Starting at just <strong className="text-emerald-400">$0.10 per lead</strong>.
          </p>

          <div className="flex flex-wrap gap-4 mb-12">
            <Link
              href="/shop?state=TX"
              className="bg-blue-600 hover:bg-blue-500 text-white font-bold px-8 py-4 rounded-xl text-lg transition-all hover:scale-105 shadow-lg shadow-blue-500/25"
            >
              Browse Texas Leads →
            </Link>
            <a
              href="#how-it-works"
              className="bg-white/10 hover:bg-white/20 border border-white/20 text-white font-semibold px-8 py-4 rounded-xl text-lg transition-all"
            >
              How It Works
            </a>
          </div>

          <div className="flex flex-wrap gap-6 text-sm text-slate-400">
            {["No subscription required", "Instant CSV download", "Pay only for what you need", "All Texas cities"].map(
              (item) => (
                <span key={item} className="flex items-center gap-2">
                  <svg className="w-4 h-4 text-emerald-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                  </svg>
                  {item}
                </span>
              )
            )}
          </div>
        </div>
      </div>

      {/* Stats strip */}
      <div className="border-t border-white/10 bg-black/20">
        <div className="max-w-6xl mx-auto px-6 py-6 grid grid-cols-2 md:grid-cols-5 gap-6 text-center">
          {[
            { value: formatted, label: "Texas leads" },
            { value: intentFormatted, label: "Intent leads" },
            { value: "85+", label: "Industries" },
            { value: "$0.10", label: "Starting price" },
            { value: "Instant", label: "CSV delivery" },
          ].map(({ value, label }) => (
            <div key={label}>
              <div className="text-2xl font-bold text-white">{value}</div>
              <div className="text-sm text-slate-400 mt-0.5">{label}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
