import type { Metadata } from "next";
import Link from "next/link";

export const revalidate = 3600;

interface PageSummary {
  industry: string;
  city: string;
  state: string;
  count: number;
  slug_industry: string;
  slug_city: string;
}

async function getPagesForIndustry(slugIndustry: string): Promise<PageSummary[]> {
  try {
    const res = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL}/api/seo/pages?min_count=5`,
      { next: { revalidate: 3600 } }
    );
    if (!res.ok) return [];
    const all: PageSummary[] = await res.json();
    return all.filter((p) => p.slug_industry === slugIndustry);
  } catch {
    return [];
  }
}

export async function generateMetadata({
  params,
}: {
  params: { industry: string };
}): Promise<Metadata> {
  const industryTitle = params.industry.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  return {
    title: `${industryTitle} Leads in Texas | Take Your Lead Today`,
    description: `Buy verified ${industryTitle} leads across every major Texas city. Homeowners and businesses actively in-market. Instant download, starting at $0.10/lead.`,
  };
}

export default async function IndustryPage({ params }: { params: { industry: string } }) {
  const pages = await getPagesForIndustry(params.industry);
  const industryTitle = params.industry.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  const total = pages.reduce((s, p) => s + p.count, 0);

  return (
    <div className="max-w-6xl mx-auto px-6 py-12">
      <div className="mb-3 text-sm text-slate-500">
        <Link href="/leads" className="hover:text-blue-600">All Industries</Link>
        {" / "}
        <span>{industryTitle}</span>
      </div>

      <h1 className="text-4xl font-black text-slate-900 mb-3">
        {industryTitle} Leads in Texas
      </h1>
      <p className="text-lg text-slate-600 mb-10 max-w-2xl">
        {total.toLocaleString()} verified {industryTitle.toLowerCase()} leads across{" "}
        {pages.length} Texas cities. Sourced from building permits, state licensing databases,
        and business directories. Instant CSV download.
      </p>

      {pages.length === 0 ? (
        <div className="text-slate-500 py-20 text-center">No leads found for this industry yet.</div>
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {pages
            .sort((a, b) => b.count - a.count)
            .map((p) => (
              <Link
                key={p.slug_city}
                href={`/leads/${p.slug_industry}/${p.slug_city}`}
                className="border border-slate-200 hover:border-blue-300 hover:bg-blue-50
                           rounded-xl p-5 transition-all group"
              >
                <div className="font-bold text-slate-900 group-hover:text-blue-700 text-lg">
                  {p.city}, {p.state}
                </div>
                <div className="text-slate-500 text-sm mt-1">
                  {p.count.toLocaleString()} leads available
                </div>
                <div className="text-blue-600 text-sm font-medium mt-3 group-hover:translate-x-1 transition-transform inline-block">
                  Browse leads →
                </div>
              </Link>
            ))}
        </div>
      )}

      <div className="mt-12 bg-blue-50 border border-blue-200 rounded-xl p-8 text-center">
        <h2 className="text-2xl font-bold text-slate-900 mb-2">
          Ready to buy {industryTitle} leads?
        </h2>
        <p className="text-slate-600 mb-6">
          Search by city, filter by quality, and download instantly. Starting at $0.10/lead.
        </p>
        <Link
          href={`/shop?industry=${encodeURIComponent(industryTitle)}&state=TX`}
          className="bg-blue-600 hover:bg-blue-700 text-white font-bold px-8 py-3 rounded-lg transition-all inline-block"
        >
          Shop {industryTitle} Leads →
        </Link>
      </div>
    </div>
  );
}
