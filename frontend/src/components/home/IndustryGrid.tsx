import Link from "next/link";
import type { IndustryStat } from "@/types";

const INDUSTRY_ICONS: Record<string, string> = {
  Roofing: "🏠",
  Plumbing: "🔧",
  Hvac: "❄️",
  Solar: "☀️",
  Electrician: "⚡",
  Landscaping: "🌿",
  "Pest Control": "🐛",
  Construction: "🏗️",
  Insurance: "🛡️",
  "Law Firm": "⚖️",
  Dentist: "🦷",
  Medical: "🏥",
  "Real Estate": "🏢",
  Restaurant: "🍽️",
};

const POPULAR_INDUSTRIES = [
  { industry: "Roofing", state: "TX" },
  { industry: "Plumbing", state: "TX" },
  { industry: "Hvac", state: "TX" },
  { industry: "Solar", state: "TX" },
  { industry: "Electrician", state: "TX" },
  { industry: "Landscaping", state: "TX" },
  { industry: "Pest Control", state: "TX" },
  { industry: "Remodeling", state: "TX" },
];

export default function IndustryGrid({ industries }: { industries: IndustryStat[] }) {
  const industryMap = new Map(industries.map((i) => [i.industry.toLowerCase(), i.count]));

  const displayItems = POPULAR_INDUSTRIES.map(({ industry, state }) => ({
    industry,
    state,
    count: industryMap.get(industry.toLowerCase()) ?? 0,
    icon: INDUSTRY_ICONS[industry] ?? "📋",
  }));

  return (
    <section className="py-20 bg-slate-50">
      <div className="max-w-6xl mx-auto px-6">
        <div className="text-center mb-14">
          <h2 className="text-3xl lg:text-4xl font-bold text-slate-900 mb-4">Browse Texas Leads by Industry</h2>
          <p className="text-slate-500 text-lg">
            Click any industry to see available Texas leads and pricing.
          </p>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
          {displayItems.map(({ industry, state, count, icon }) => (
            <Link
              key={`${industry}-${state}`}
              href={`/shop?industry=${encodeURIComponent(industry)}&state=${state}`}
              className="group bg-white rounded-2xl p-6 border border-slate-200 hover:border-blue-300 hover:shadow-md transition-all"
            >
              <div className="text-3xl mb-3">{icon}</div>
              <div className="font-bold text-slate-800 group-hover:text-blue-600 transition-colors">
                {industry}
              </div>
              {count > 0 ? (
                <div className="text-sm text-emerald-600 font-medium mt-1">
                  {count.toLocaleString()} leads
                </div>
              ) : (
                <div className="text-sm text-slate-400 mt-1">Browse →</div>
              )}
            </Link>
          ))}
        </div>

        <div className="text-center mt-8">
          <Link
            href="/shop"
            className="inline-flex items-center gap-2 text-blue-600 font-semibold hover:text-blue-700 transition-colors"
          >
            Search all industries
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </Link>
        </div>
      </div>
    </section>
  );
}
