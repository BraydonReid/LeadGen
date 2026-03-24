import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Contractor & Business Leads by Industry | Take Your Lead Today",
  description:
    "Browse verified contractor and business leads by industry. Roofing, HVAC, plumbing, electrician, solar, landscaping and 80+ more industries across every city.",
};

export const revalidate = 3600; // ISR: rebuild every hour

interface PageSummary {
  industry: string;
  city: string;
  state: string;
  count: number;
  slug_industry: string;
  slug_city: string;
}

async function getPages(): Promise<PageSummary[]> {
  try {
    const res = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL}/api/seo/pages?min_count=10`,
      { next: { revalidate: 3600 } }
    );
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

export default async function LeadsDirectoryPage() {
  const pages = await getPages();

  // Group by industry for display
  const byIndustry: Record<string, PageSummary[]> = {};
  for (const p of pages) {
    if (!byIndustry[p.industry]) byIndustry[p.industry] = [];
    byIndustry[p.industry].push(p);
  }

  const industries = Object.keys(byIndustry).sort();
  const totalLeads = pages.reduce((sum, p) => sum + p.count, 0);

  return (
    <div className="max-w-6xl mx-auto px-6 py-12">
      {/* Header */}
      <div className="mb-10">
        <h1 className="text-4xl font-black text-slate-900 mb-3">
          Contractor &amp; Business Leads by Industry
        </h1>
        <p className="text-lg text-slate-600 max-w-2xl">
          {totalLeads.toLocaleString()}+ verified leads across {industries.length} industries
          and every major Texas city. Instant CSV download, starting at $0.10/lead.
        </p>
      </div>

      {/* Industry grid */}
      <div className="space-y-10">
        {industries.map((industry) => {
          const cities = byIndustry[industry].slice(0, 8);
          const slug = cities[0]?.slug_industry ?? industry.toLowerCase().replace(/ /g, "-");
          const totalForIndustry = byIndustry[industry].reduce((s, p) => s + p.count, 0);

          return (
            <div key={industry} className="border border-slate-200 rounded-xl p-6">
              <div className="flex items-baseline justify-between mb-4">
                <h2 className="text-xl font-bold text-slate-900 capitalize">{industry} Leads in Texas</h2>
                <span className="text-sm text-slate-500">{totalForIndustry.toLocaleString()} leads</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {cities.map((p) => (
                  <Link
                    key={`${p.slug_industry}/${p.slug_city}`}
                    href={`/leads/${p.slug_industry}/${p.slug_city}`}
                    className="bg-slate-100 hover:bg-blue-50 hover:text-blue-700 text-slate-700
                               px-3 py-1.5 rounded-full text-sm font-medium transition-colors"
                  >
                    {p.city} ({p.count.toLocaleString()})
                  </Link>
                ))}
                {byIndustry[industry].length > 8 && (
                  <Link
                    href={`/leads/${slug}`}
                    className="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-full text-sm font-medium transition-colors"
                  >
                    +{byIndustry[industry].length - 8} more cities →
                  </Link>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-12 text-center">
        <Link
          href="/shop"
          className="bg-blue-600 hover:bg-blue-700 text-white font-bold px-8 py-4 rounded-xl text-lg transition-all inline-block"
        >
          Browse All Leads →
        </Link>
      </div>
    </div>
  );
}
