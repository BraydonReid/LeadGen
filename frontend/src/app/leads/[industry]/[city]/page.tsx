import type { Metadata } from "next";
import Link from "next/link";

export const revalidate = 3600;

interface SampleLead {
  business_name: string;
  city: string;
  state: string;
  quality_score: number | null;
  yelp_rating: number | null;
  review_count: number | null;
  lead_type: string;
}

interface PageData {
  industry: string;
  city: string;
  state: string;
  count: number;
  avg_price: number;
  sample_leads: SampleLead[];
  related_industries: string[];
  related_cities: string[];
}

async function getPageData(slugIndustry: string, slugCity: string): Promise<PageData | null> {
  try {
    const res = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL}/api/seo/page/${slugIndustry}/${slugCity}`,
      { next: { revalidate: 3600 } }
    );
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

function qualityLabel(score: number | null) {
  if (!score) return null;
  if (score >= 70) return { label: "High Quality", color: "bg-green-100 text-green-800" };
  if (score >= 40) return { label: "Good", color: "bg-yellow-100 text-yellow-800" };
  return { label: "Standard", color: "bg-slate-100 text-slate-600" };
}

export async function generateMetadata({
  params,
}: {
  params: { industry: string; city: string };
}): Promise<Metadata> {
  const data = await getPageData(params.industry, params.city);
  const industryTitle = params.industry.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  const cityParts = params.city.split("-");
  const state = cityParts.pop()?.toUpperCase() ?? "TX";
  const cityName = cityParts.join(" ").replace(/\b\w/g, (c) => c.toUpperCase());

  return {
    title: `Buy ${industryTitle} Leads in ${cityName}, ${state} | Take Your Lead Today`,
    description: `${data?.count ?? "Hundreds of"} verified ${industryTitle.toLowerCase()} leads in ${cityName}, ${state}. Includes homeowners with active permits and local businesses. Starting at $${data?.avg_price?.toFixed(2) ?? "0.25"}/lead. Instant download.`,
    openGraph: {
      title: `${industryTitle} Leads in ${cityName}, ${state}`,
      description: `${data?.count ?? 0} verified leads — buy and download instantly.`,
    },
  };
}

export default async function CityIndustryPage({
  params,
}: {
  params: { industry: string; city: string };
}) {
  const data = await getPageData(params.industry, params.city);
  const industryTitle = params.industry.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

  const cityParts0 = params.city.split("-");
  const state0 = cityParts0.pop()?.toUpperCase() ?? "TX";
  const cityName0 = cityParts0.join(" ").replace(/\b\w/g, (c) => c.toUpperCase());

  const jsonLd = data
    ? {
        "@context": "https://schema.org",
        "@type": "ItemList",
        name: `${industryTitle} Leads in ${cityName0}, ${state0}`,
        description: `${data.count} verified ${industryTitle.toLowerCase()} leads in ${cityName0}, ${state0}`,
        numberOfItems: data.count,
        itemListElement: data.sample_leads.slice(0, 5).map((lead, i) => ({
          "@type": "ListItem",
          position: i + 1,
          item: {
            "@type": "LocalBusiness",
            name: lead.business_name,
            address: {
              "@type": "PostalAddress",
              addressLocality: lead.city,
              addressRegion: lead.state,
              addressCountry: "US",
            },
            ...(lead.yelp_rating != null
              ? {
                  aggregateRating: {
                    "@type": "AggregateRating",
                    ratingValue: lead.yelp_rating,
                    reviewCount: lead.review_count ?? 1,
                    bestRating: 5,
                    worstRating: 1,
                  },
                }
              : {}),
          },
        })),
      }
    : null;

  const cityParts = params.city.split("-");
  const state = cityParts.pop()?.toUpperCase() ?? "TX";
  const cityName = cityParts.join(" ").replace(/\b\w/g, (c) => c.toUpperCase());

  if (!data) {
    return (
      <div className="max-w-4xl mx-auto px-6 py-20 text-center">
        <h1 className="text-3xl font-bold text-slate-900 mb-4">
          {industryTitle} Leads in {cityName}, {state}
        </h1>
        <p className="text-slate-500 mb-8">We&apos;re still collecting leads for this location.</p>
        <Link href="/shop" className="bg-blue-600 text-white font-bold px-6 py-3 rounded-lg">
          Browse All Leads →
        </Link>
      </div>
    );
  }

  const shopUrl = `/shop?industry=${encodeURIComponent(industryTitle)}&state=${state}&city=${encodeURIComponent(cityName)}`;
  const sampleUrl = `${shopUrl}&sample=1`;

  return (
    <div className="max-w-5xl mx-auto px-6 py-12">
      {jsonLd && (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
      )}
      {/* Breadcrumb */}
      <div className="mb-4 text-sm text-slate-500 flex gap-2 flex-wrap">
        <Link href="/leads" className="hover:text-blue-600">All Industries</Link>
        <span>/</span>
        <Link href={`/leads/${params.industry}`} className="hover:text-blue-600">{industryTitle}</Link>
        <span>/</span>
        <span>{cityName}, {state}</span>
      </div>

      {/* Hero */}
      <div className="mb-10">
        <div className="flex items-center gap-3 mb-3">
          <span className="bg-blue-100 text-blue-800 text-sm font-semibold px-3 py-1 rounded-full">
            {data.count.toLocaleString()} Leads Available
          </span>
          {data.sample_leads.some(l => l.lead_type === "consumer") && (
            <span className="bg-orange-100 text-orange-800 text-sm font-semibold px-3 py-1 rounded-full">
              Includes Consumer Intent Leads
            </span>
          )}
        </div>
        <h1 className="text-4xl font-black text-slate-900 mb-3">
          {industryTitle} Leads in {cityName}, {state}
        </h1>
        <p className="text-lg text-slate-600 max-w-2xl">
          {data.count.toLocaleString()} verified {industryTitle.toLowerCase()} leads in {cityName}.
          Sourced from building permits, state licensing databases, and business directories.
          Avg. <strong>${data.avg_price.toFixed(2)}/lead</strong>. Download instantly as CSV.
        </p>

        <div className="flex gap-4 mt-6 flex-wrap">
          <Link
            href={shopUrl}
            className="bg-blue-600 hover:bg-blue-700 text-white font-bold px-6 py-3 rounded-xl transition-all"
          >
            Buy {industryTitle} Leads in {cityName} →
          </Link>
          <Link
            href={sampleUrl}
            className="border border-blue-300 text-blue-600 hover:bg-blue-50 font-semibold px-6 py-3 rounded-xl transition-all"
          >
            Get 5 Free Sample Leads
          </Link>
        </div>
      </div>

      {/* Sample leads */}
      {data.sample_leads.length > 0 && (
        <div className="mb-12">
          <h2 className="text-xl font-bold text-slate-900 mb-4">
            Sample {industryTitle} Leads in {cityName}
          </h2>
          <div className="border border-slate-200 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th className="text-left px-4 py-3 font-semibold text-slate-700">Business</th>
                  <th className="text-left px-4 py-3 font-semibold text-slate-700">Location</th>
                  <th className="text-left px-4 py-3 font-semibold text-slate-700">Quality</th>
                  <th className="text-left px-4 py-3 font-semibold text-slate-700">Rating</th>
                  <th className="text-left px-4 py-3 font-semibold text-slate-700">Type</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.sample_leads.map((lead, i) => {
                  const q = qualityLabel(lead.quality_score);
                  return (
                    <tr key={i} className="hover:bg-slate-50">
                      <td className="px-4 py-3 font-medium text-slate-900">{lead.business_name}</td>
                      <td className="px-4 py-3 text-slate-600">{lead.city}, {lead.state}</td>
                      <td className="px-4 py-3">
                        {q && (
                          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${q.color}`}>
                            {q.label}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-slate-600">
                        {lead.yelp_rating ? `⭐ ${lead.yelp_rating} (${lead.review_count})` : "—"}
                      </td>
                      <td className="px-4 py-3">
                        {lead.lead_type === "consumer" ? (
                          <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-orange-100 text-orange-800">
                            Active Permit
                          </span>
                        ) : (
                          <span className="text-xs text-slate-500">Business</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <div className="bg-slate-50 border-t border-slate-200 px-4 py-3 text-sm text-slate-500 text-center">
              Showing 5 of {data.count.toLocaleString()} leads. Phone numbers, emails, and full
              addresses included in download.
            </div>
          </div>
        </div>
      )}

      {/* Why these leads */}
      <div className="grid md:grid-cols-3 gap-6 mb-12">
        {[
          {
            title: "Verified & Fresh",
            body: "Sourced daily from building permits and state licensing databases. Only leads from the last 90 days.",
          },
          {
            title: "Full Contact Info",
            body: "Phone number, address, and website included on every lead. Many include Yelp ratings and review counts.",
          },
          {
            title: "Instant Download",
            body: "Pay once, download immediately as CSV. Import into any CRM, dialer, or spreadsheet in seconds.",
          },
        ].map((card) => (
          <div key={card.title} className="bg-slate-50 rounded-xl p-6">
            <h3 className="font-bold text-slate-900 mb-2">{card.title}</h3>
            <p className="text-slate-600 text-sm">{card.body}</p>
          </div>
        ))}
      </div>

      {/* FAQ — schema markup */}
      <div className="mb-12">
        <h2 className="text-2xl font-bold text-slate-900 mb-6">
          Frequently Asked Questions
        </h2>
        <div className="space-y-4">
          {[
            {
              q: `How many ${industryTitle.toLowerCase()} leads are available in ${cityName}?`,
              a: `We currently have ${data.count.toLocaleString()} verified ${industryTitle.toLowerCase()} leads in ${cityName}, ${state}. New leads are added daily as our scrapers pull from building permits and state licensing records.`,
            },
            {
              q: `How much do ${industryTitle.toLowerCase()} leads in ${cityName} cost?`,
              a: `Leads start at $0.10 each with bulk discounts up to 45% off. The average ${industryTitle.toLowerCase()} lead in ${cityName} is $${data.avg_price.toFixed(2)}. AI-scored and consumer-intent leads are priced slightly higher due to their higher conversion rate.`,
            },
            {
              q: "What contact information is included?",
              a: "Every lead includes business name, phone number, full address, and website (where available). High-quality leads also include Yelp ratings, review counts, and a named contact.",
            },
            {
              q: "What are consumer intent leads?",
              a: `Consumer intent leads are homeowners who recently pulled a ${industryTitle.toLowerCase()} building permit — meaning they're actively in the market right now. These are the highest-converting leads and are marked with an "Active Permit" tag.`,
            },
            {
              q: "Do the leads include email addresses?",
              a: "Yes — many leads include verified email addresses discovered via SMTP verification and website scraping. Email coverage varies by industry and city, typically 15–40% of leads. Every lead includes phone number and address.",
            },
            {
              q: "How many times is each lead sold?",
              a: "We enforce a hard maximum of 5 sales per lead. Once a lead reaches 5 buyers it is permanently retired from the shop. Most competitors sell the same lead to unlimited buyers without disclosing this.",
            },
            {
              q: "What's your bad lead guarantee?",
              a: "If a lead has a disconnected phone, wrong address, or is otherwise unusable, report it and we'll issue a store credit — no questions asked. Use the Report button in your order confirmation email.",
            },
          ].map((faq) => (
            <details key={faq.q} className="border border-slate-200 rounded-xl p-5 group">
              <summary className="font-semibold text-slate-900 cursor-pointer list-none flex justify-between items-center">
                {faq.q}
                <span className="text-slate-400 group-open:rotate-180 transition-transform">▼</span>
              </summary>
              <p className="mt-3 text-slate-600 text-sm leading-relaxed">{faq.a}</p>
            </details>
          ))}
        </div>
      </div>

      {/* Related */}
      <div className="grid md:grid-cols-2 gap-8 mb-12">
        {data.related_cities.length > 0 && (
          <div>
            <h3 className="font-bold text-slate-900 mb-3">
              {industryTitle} Leads in Nearby Cities
            </h3>
            <div className="flex flex-wrap gap-2">
              {data.related_cities.map((city) => {
                const [c, s] = city.split(", ");
                const slug = `${c.toLowerCase().replace(/ /g, "-")}-${s?.toLowerCase() ?? "tx"}`;
                return (
                  <Link
                    key={city}
                    href={`/leads/${params.industry}/${slug}`}
                    className="bg-slate-100 hover:bg-blue-50 hover:text-blue-700 text-slate-700
                               px-3 py-1.5 rounded-full text-sm font-medium transition-colors"
                  >
                    {city}
                  </Link>
                );
              })}
            </div>
          </div>
        )}
        {data.related_industries.length > 0 && (
          <div>
            <h3 className="font-bold text-slate-900 mb-3">
              Other Contractor Leads in {cityName}
            </h3>
            <div className="flex flex-wrap gap-2">
              {data.related_industries.map((ind) => {
                const slug = ind.toLowerCase().replace(/ /g, "-");
                return (
                  <Link
                    key={ind}
                    href={`/leads/${slug}/${params.city}`}
                    className="bg-slate-100 hover:bg-blue-50 hover:text-blue-700 text-slate-700
                               px-3 py-1.5 rounded-full text-sm font-medium transition-colors capitalize"
                  >
                    {ind}
                  </Link>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* CTA */}
      <div className="bg-blue-600 rounded-2xl p-8 text-center text-white">
        <h2 className="text-2xl font-black mb-2">
          Ready to buy {industryTitle} leads in {cityName}?
        </h2>
        <p className="text-blue-100 mb-6">
          {data.count.toLocaleString()} leads available. Instant download. No subscription required.
        </p>
        <div className="flex gap-4 justify-center flex-wrap">
          <Link
            href={shopUrl}
            className="bg-white text-blue-600 hover:bg-blue-50 font-bold px-8 py-3 rounded-xl transition-all"
          >
            Buy Leads Now →
          </Link>
          <Link
            href={sampleUrl}
            className="border border-blue-300 text-white hover:bg-blue-700 font-semibold px-8 py-3 rounded-xl transition-all"
          >
            Get 5 Free First
          </Link>
        </div>
      </div>
    </div>
  );
}
