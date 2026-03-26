import ComparisonTable from "@/components/home/ComparisonTable";
import ConsumerPortalCTA from "@/components/home/ConsumerPortalCTA";
import CsvPreview from "@/components/home/CsvPreview";
import DataQualityBar from "@/components/home/DataQualityBar";
import Features from "@/components/home/Features";
import Hero from "@/components/home/Hero";
import HowItWorks from "@/components/home/HowItWorks";
import IndustryGrid from "@/components/home/IndustryGrid";
import { getStats } from "@/lib/api";
import Link from "next/link";

export default async function HomePage() {
  const stats = await getStats();

  return (
    <>
      <Hero totalLeads={stats.total_leads} consumerIntentCount={stats.consumer_intent_count} />
      <DataQualityBar
        pctPhone={stats.pct_with_phone}
        pctEmail={stats.pct_with_email}
        pctContact={stats.pct_with_contact}
        pctAddress={stats.pct_with_address}
      />
      <HowItWorks />
      <ComparisonTable />
      <ConsumerPortalCTA intentLeadCount={stats.consumer_intent_count} />
      <Features />

      <section id="industries">
        <IndustryGrid industries={stats.industries} />
      </section>

      {/* CTA */}
      <section className="py-20 bg-white">
        <div className="max-w-4xl mx-auto px-6 text-center">
          <div className="bg-gradient-to-br from-blue-600 to-blue-800 rounded-3xl p-10 lg:p-16 text-white shadow-xl shadow-blue-500/20">
            <h2 className="text-3xl lg:text-4xl font-bold mb-4">
              The freshest contractor leads in Texas
            </h2>
            <p className="text-blue-100 text-lg mb-3 max-w-2xl mx-auto leading-relaxed">
              Traditional lead services charge thousands per month and lock you into long contracts.
              We built Take Your Lead Today so any Texas contractor can access quality local leads — without the overhead.
            </p>
            <p className="text-blue-200 text-base mb-10 max-w-xl mx-auto">
              No phone calls to sales reps. Pick your city and industry,
              choose how many leads you need, and download your CSV in minutes.
              98% have a verified phone number.
            </p>
            <div className="flex flex-wrap justify-center gap-4">
              <Link
                href="/shop?state=TX"
                className="bg-white text-blue-700 font-bold px-8 py-4 rounded-xl text-lg hover:bg-blue-50 transition-all hover:scale-105"
              >
                Browse Texas Leads →
              </Link>
              <Link
                href="/pricing"
                className="border border-white/30 text-white font-semibold px-8 py-4 rounded-xl text-lg hover:bg-white/10 transition-all"
              >
                See Pricing →
              </Link>
            </div>
          </div>
        </div>
      </section>

      <CsvPreview />

      {/* Pricing preview */}
      <section className="py-20 bg-slate-50">
        <div className="max-w-6xl mx-auto px-6">
          <div className="text-center mb-12">
            <h2 className="text-3xl lg:text-4xl font-bold text-slate-900 mb-4">Simple, Transparent Pricing</h2>
            <p className="text-slate-500 text-lg max-w-xl mx-auto">
              Pay per lead — no subscriptions. The more you buy, the less you pay per lead.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-6 max-w-3xl mx-auto mb-10">
            {[
              { qty: "100", example: "$0.72", total: "~$72", discount: "10% off", popular: false },
              { qty: "500", example: "$0.66", total: "~$330", discount: "18% off", popular: true },
              { qty: "1,000", example: "$0.54", total: "~$540", discount: "25% off", popular: false },
            ].map(({ qty, example, total, discount, popular }) => (
              <div
                key={qty}
                className={`bg-white rounded-2xl p-6 border-2 text-center ${popular ? "border-blue-500 shadow-lg" : "border-slate-200"}`}
              >
                {popular && (
                  <div className="text-xs font-bold text-blue-600 uppercase tracking-wider mb-2">Most Popular</div>
                )}
                <div className="text-3xl font-black text-slate-900 mb-1">{qty}</div>
                <div className="text-slate-500 text-sm mb-3">leads</div>
                <div className="text-2xl font-bold text-blue-600 mb-1">{example}/lead</div>
                <div className="text-slate-400 text-sm mb-3">Total {total}</div>
                <div className="inline-block bg-emerald-50 text-emerald-700 text-xs font-semibold px-3 py-1 rounded-full mb-4">
                  {discount}
                </div>
                <div className="block">
                  <Link href="/shop" className="text-blue-600 hover:text-blue-700 font-semibold text-sm">
                    Browse leads →
                  </Link>
                </div>
              </div>
            ))}
          </div>

          <p className="text-center text-slate-400 text-sm">
            Prices shown are examples for roofing leads in Texas. Actual prices vary by industry and city.{" "}
            <Link href="/shop?state=TX" className="text-blue-600 hover:underline">Search your Texas industry for exact pricing.</Link>
          </p>
        </div>
      </section>
    </>
  );
}
