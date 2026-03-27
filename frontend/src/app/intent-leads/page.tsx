import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Consumer Intent Leads — Homeowners Actively Seeking Contractors | Take Your Lead Today",
  description:
    "Buy consumer intent leads from building permits, code violations, and new homeowner data. Homeowners actively looking for contractors — roofing, HVAC, plumbing, solar and more. Starting at $0.15/lead.",
};

const INTENT_SOURCES = [
  {
    icon: "🏗️",
    title: "Building Permits",
    description:
      "Homeowners who have filed a building permit are actively under construction. They need subcontractors, material suppliers, and finishing trades immediately.",
    hotness: "High Intent",
    industries: ["Roofing", "HVAC", "Electrical", "Plumbing", "Remodeling"],
  },
  {
    icon: "⚠️",
    title: "Code Enforcement Violations",
    description:
      "Properties with active code violations have a legal deadline to fix the issue. A homeowner cited for a damaged roof has no choice — they must hire someone.",
    hotness: "Urgent Intent",
    industries: ["Roofing", "Fencing", "Foundation", "Siding", "Waterproofing"],
  },
  {
    icon: "🏠",
    title: "New Homeowner Transfers",
    description:
      "Properties that changed ownership in the last 90 days. New homeowners renovate at 3× the rate of existing owners within the first year of purchase.",
    hotness: "High Intent",
    industries: ["HVAC", "Flooring", "Painting", "Landscaping", "Security Systems"],
  },
  {
    icon: "💥",
    title: "Demolition Permits",
    description:
      "A demolition permit means a rebuild is coming. Filed 4–8 weeks before new construction begins — the contractor who gets there first wins the job.",
    hotness: "Extreme Intent",
    industries: ["General Contractor", "Concrete", "Framing", "Roofing", "Electrical"],
  },
];

const VS_ROWS = [
  {
    feature: "Lead type",
    intent: "Homeowner actively under construction or obligated to repair",
    cold: "Business contact with no immediate need",
  },
  {
    feature: "Conversion rate",
    intent: "5–15× higher than cold outreach",
    cold: "Baseline — requires nurturing",
  },
  {
    feature: "Price per lead",
    intent: "1.5× standard price — worth every cent",
    cold: "Standard pricing",
  },
  {
    feature: "Resales",
    intent: "Max 5 buyers — enforced in database",
    cold: "Max 5 buyers — enforced in database",
  },
  {
    feature: "Data freshness",
    intent: "Permit date included — filter by days-since",
    cold: "Scraped date included",
  },
  {
    feature: "Best for",
    intent: "Roofing, HVAC, remodeling, solar, electrical",
    cold: "Any B2B outreach campaign",
  },
];

export default function IntentLeadsPage() {
  return (
    <>
      {/* Hero */}
      <section className="bg-gradient-to-br from-slate-900 via-slate-800 to-orange-900 text-white">
        <div className="max-w-5xl mx-auto px-6 py-24 lg:py-32">
          <div className="inline-flex items-center gap-2 bg-orange-500/20 border border-orange-400/30 rounded-full px-4 py-1.5 text-sm text-orange-300 mb-8">
            <span className="w-2 h-2 bg-orange-400 rounded-full animate-pulse" />
            Highest-converting leads in our database
          </div>
          <h1 className="text-5xl lg:text-6xl font-extrabold leading-tight mb-6">
            Consumer Intent Leads.
            <br />
            <span className="text-orange-400">Homeowners Who Need You Now.</span>
          </h1>
          <p className="text-lg lg:text-xl text-slate-300 mb-10 leading-relaxed max-w-3xl">
            Every lead in this category comes from a <strong className="text-white">real-world trigger event</strong> — a
            building permit filed, a code violation issued, a home that just sold. These are not cold contacts.
            These are homeowners with an <strong className="text-orange-400">active, urgent need for a contractor</strong>.
          </p>
          <div className="flex flex-wrap gap-4 mb-12">
            <Link
              href="/shop?lead_type=consumer&state=TX"
              className="bg-orange-500 hover:bg-orange-400 text-white font-bold px-8 py-4 rounded-xl text-lg transition-all hover:scale-105 shadow-lg shadow-orange-500/25"
            >
              Browse Intent Leads →
            </Link>
            <Link
              href="/shop"
              className="bg-white/10 hover:bg-white/20 border border-white/20 text-white font-semibold px-8 py-4 rounded-xl text-lg transition-all"
            >
              Browse All Leads
            </Link>
          </div>
          <div className="flex flex-wrap gap-6 text-sm text-slate-400">
            {[
              "Sourced from public permit records",
              "Updated daily",
              "1.5× conversion rate vs cold lists",
              "Instant CSV download",
            ].map((item) => (
              <span key={item} className="flex items-center gap-2">
                <svg className="w-4 h-4 text-orange-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                </svg>
                {item}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* Intent Sources */}
      <section className="py-20 bg-white">
        <div className="max-w-5xl mx-auto px-6">
          <div className="text-center mb-14">
            <span className="inline-block bg-orange-50 text-orange-600 text-xs font-bold tracking-widest uppercase px-4 py-1.5 rounded-full mb-4">
              Data Sources
            </span>
            <h2 className="text-3xl sm:text-4xl font-black text-slate-900 mb-4">
              Where intent leads come from
            </h2>
            <p className="text-slate-500 text-lg max-w-2xl mx-auto">
              All sourced from free, public government databases. Updated daily. No scraping of private sites.
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-6">
            {INTENT_SOURCES.map((source) => (
              <div key={source.title} className="border border-slate-200 rounded-2xl p-6 hover:border-orange-200 hover:shadow-md transition-all">
                <div className="flex items-start justify-between mb-4">
                  <div className="text-3xl">{source.icon}</div>
                  <span className={`text-xs font-bold px-3 py-1 rounded-full ${
                    source.hotness === "Extreme Intent"
                      ? "bg-red-100 text-red-700"
                      : source.hotness === "Urgent Intent"
                      ? "bg-orange-100 text-orange-700"
                      : "bg-amber-100 text-amber-700"
                  }`}>
                    {source.hotness}
                  </span>
                </div>
                <h3 className="text-xl font-bold text-slate-900 mb-2">{source.title}</h3>
                <p className="text-slate-600 text-sm leading-relaxed mb-4">{source.description}</p>
                <div className="flex flex-wrap gap-1.5">
                  {source.industries.map((ind) => (
                    <span key={ind} className="text-xs bg-slate-100 text-slate-600 px-2.5 py-1 rounded-full font-medium">
                      {ind}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Intent vs Cold comparison */}
      <section className="py-20 bg-slate-50">
        <div className="max-w-5xl mx-auto px-6">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-black text-slate-900 mb-4">Intent leads vs. standard directory leads</h2>
            <p className="text-slate-500 text-lg max-w-xl mx-auto">
              Same download format, same instant CSV. Totally different conversion story.
            </p>
          </div>

          <div className="rounded-2xl border border-slate-200 overflow-hidden shadow-sm">
            <div className="grid grid-cols-3 bg-slate-900 text-white text-sm font-semibold">
              <div className="px-6 py-4 text-slate-400">Feature</div>
              <div className="px-6 py-4 text-orange-300 border-l border-slate-700">Consumer Intent Lead</div>
              <div className="px-6 py-4 text-slate-400 border-l border-slate-700">Standard Directory Lead</div>
            </div>
            {VS_ROWS.map((row, i) => (
              <div
                key={row.feature}
                className={`grid grid-cols-3 text-sm border-t border-slate-100 ${i % 2 === 0 ? "bg-white" : "bg-slate-50"}`}
              >
                <div className="px-6 py-4 font-medium text-slate-700 flex items-center">{row.feature}</div>
                <div className="px-6 py-4 border-l border-slate-100 text-slate-700 flex items-center gap-2">
                  <span className="w-5 h-5 bg-orange-100 rounded-full flex items-center justify-center shrink-0">
                    <svg className="w-3 h-3 text-orange-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  </span>
                  {row.intent}
                </div>
                <div className="px-6 py-4 border-l border-slate-100 text-slate-500 flex items-center">{row.cold}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing note */}
      <section className="py-16 bg-white">
        <div className="max-w-3xl mx-auto px-6 text-center">
          <h2 className="text-2xl font-bold text-slate-900 mb-4">Pricing</h2>
          <p className="text-slate-600 mb-6 text-lg leading-relaxed">
            Consumer intent leads are priced at <strong>1.5× the standard lead price</strong> for the same
            industry and city. A roofing lead that costs $0.55 on the standard list costs ~$0.82 as an intent lead.
            Given the conversion rate difference, the effective cost-per-customer is still lower.
          </p>
          <div className="bg-orange-50 border border-orange-100 rounded-2xl p-6 text-left mb-8">
            <div className="font-semibold text-slate-900 mb-2">Example: Houston Roofing</div>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <div className="text-slate-500 mb-1">Standard directory lead</div>
                <div className="font-bold text-slate-800">~$0.55/lead</div>
                <div className="text-slate-400 mt-1">Cold outreach — may or may not need service</div>
              </div>
              <div>
                <div className="text-slate-500 mb-1">Consumer intent lead</div>
                <div className="font-bold text-orange-600">~$0.82/lead</div>
                <div className="text-slate-400 mt-1">Filed a permit this week — actively building</div>
              </div>
            </div>
          </div>
          <Link
            href="/shop?lead_type=consumer&state=TX"
            className="inline-block bg-orange-500 hover:bg-orange-400 text-white font-bold px-10 py-4 rounded-xl text-lg transition-all hover:scale-105"
          >
            Browse Consumer Intent Leads →
          </Link>
          <div className="mt-4 text-sm text-slate-400">
            No subscription required · Instant CSV · Max 5 resales per lead
          </div>
        </div>
      </section>
    </>
  );
}
