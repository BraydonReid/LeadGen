import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Pricing — Take Your Lead Today | Pay Per Lead or Subscribe Monthly",
  description:
    "Pay per download with no subscription, or go Pro for unlimited monthly leads. Starting at $0.10/lead. No contracts, cancel anytime.",
};

const PAY_AS_YOU_GO = [
  { qty: "100 leads", price: "$0.72", total: "~$72", discount: "10% off", href: "/shop" },
  { qty: "500 leads", price: "$0.66", total: "~$330", discount: "18% off", href: "/shop", popular: true },
  { qty: "1,000 leads", price: "$0.54", total: "~$540", discount: "25% off", href: "/shop" },
  { qty: "5,000 leads", price: "$0.46", total: "~$2,300", discount: "35% off", href: "/shop" },
  { qty: "10,000+ leads", price: "$0.39", total: "Ask us", discount: "45% off", href: "/shop" },
];

const SUBSCRIPTION_PLANS = [
  {
    name: "Starter",
    price: "$29.99",
    period: "/month",
    leads: "50 leads/month",
    perLead: "~$0.60/lead",
    features: [
      "50 fresh leads every month",
      "Any industry + any state",
      "Instant CSV download, any time",
      "Cancel anytime",
    ],
    cta: "Get Started",
    ctaHref: "/subscribe?plan=starter",
    color: "border-slate-200",
    badge: null,
  },
  {
    name: "Pro",
    price: "$99.99",
    period: "/month",
    leads: "300 leads/month",
    perLead: "~$0.33/lead",
    features: [
      "300 fresh leads every month",
      "Any industry + any state",
      "Advanced filters (Yelp, freshness, quality)",
      "AI conversion scores on all leads",
      "Instant CSV download, any time",
      "Cancel anytime",
    ],
    cta: "Subscribe Now",
    ctaHref: "/subscribe?plan=pro",
    color: "border-blue-500",
    badge: "Most Popular",
  },
];

export default function PricingPage() {
  return (
    <div className="bg-white">
      {/* Header */}
      <div className="max-w-4xl mx-auto px-6 pt-16 pb-12 text-center">
        <span className="inline-block bg-blue-50 text-blue-600 text-xs font-bold tracking-widest uppercase px-4 py-1.5 rounded-full mb-4">
          Pricing
        </span>
        <h1 className="text-4xl lg:text-5xl font-black text-slate-900 mb-4">
          Pay per lead. Or go monthly.
        </h1>
        <p className="text-lg text-slate-500 max-w-xl mx-auto">
          Start with pay-as-you-go — no commitment. When you&apos;re ready to scale,
          monthly plans cut your cost per lead by up to 65%.
        </p>
      </div>

      {/* Pay as you go */}
      <section className="max-w-5xl mx-auto px-6 pb-16">
        <h2 className="text-2xl font-bold text-slate-900 mb-2">Pay As You Go</h2>
        <p className="text-slate-500 mb-6">No subscription. Buy exactly what you need, whenever you need it.</p>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
          {PAY_AS_YOU_GO.map(({ qty, price, total, discount, href, popular }) => (
            <div
              key={qty}
              className={`border-2 rounded-2xl p-5 text-center flex flex-col ${popular ? "border-blue-500 shadow-lg" : "border-slate-200"}`}
            >
              {popular && (
                <div className="text-xs font-bold text-blue-600 uppercase tracking-wider mb-2">Most Popular</div>
              )}
              <div className="text-slate-700 font-semibold text-sm mb-2">{qty}</div>
              <div className="text-3xl font-black text-slate-900 mb-1">{price}</div>
              <div className="text-slate-400 text-xs mb-2">per lead · {total}</div>
              <div className="inline-block bg-emerald-50 text-emerald-700 text-xs font-semibold px-2 py-0.5 rounded-full mb-4">
                {discount}
              </div>
              <Link
                href={href}
                className="mt-auto bg-blue-600 hover:bg-blue-700 text-white font-semibold text-sm px-4 py-2 rounded-xl transition-all"
              >
                Browse leads →
              </Link>
            </div>
          ))}
        </div>

        <p className="text-slate-400 text-xs mt-4">
          Prices shown are examples for roofing leads in Texas. Actual prices vary by industry, city, and lead type.
          AI-scored and consumer intent leads carry a small premium.
        </p>
      </section>

      {/* Subscription plans */}
      <section className="bg-slate-50 py-16">
        <div className="max-w-5xl mx-auto px-6">
          <div className="text-center mb-10">
            <span className="inline-block bg-emerald-100 text-emerald-700 text-xs font-bold tracking-widest uppercase px-4 py-1.5 rounded-full mb-4">
              Now Live
            </span>
            <h2 className="text-3xl font-black text-slate-900 mb-3">Monthly Subscription</h2>
            <p className="text-slate-500 max-w-xl mx-auto">
              Get 300 fresh leads delivered every month. Any industry, any state.
              Download whenever you need them — no searching required.
            </p>
          </div>

          <div className="grid sm:grid-cols-2 gap-6 max-w-2xl mx-auto mb-10">
            {SUBSCRIPTION_PLANS.map((plan) => (
              <div
                key={plan.name}
                className={`bg-white rounded-2xl border-2 ${plan.color} p-7 flex flex-col`}
              >
                {plan.badge && (
                  <div className="text-xs font-bold uppercase tracking-wider mb-3 text-blue-600">
                    {plan.badge}
                  </div>
                )}
                <div className="text-xl font-black text-slate-900 mb-1">{plan.name}</div>
                <div className="flex items-baseline gap-1 mb-1">
                  <span className="text-4xl font-black text-slate-900">{plan.price}</span>
                  <span className="text-slate-400 text-sm">{plan.period}</span>
                </div>
                <div className="text-blue-600 font-semibold text-sm mb-1">{plan.leads}</div>
                <div className="text-slate-400 text-xs mb-6">{plan.perLead}</div>

                <ul className="space-y-2.5 mb-8 flex-1">
                  {plan.features.map((f) => (
                    <li key={f} className="flex items-start gap-2 text-sm text-slate-600">
                      <svg className="w-4 h-4 text-emerald-500 mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                      </svg>
                      {f}
                    </li>
                  ))}
                </ul>

                <Link
                  href={plan.ctaHref}
                  className="text-center font-bold py-3 rounded-xl transition-all text-sm bg-blue-600 hover:bg-blue-700 text-white"
                >
                  {plan.cta}
                </Link>
              </div>
            ))}
          </div>

          {/* Already subscribed link */}
          <div className="text-center">
            <p className="text-slate-500 text-sm">
              Already subscribed?{" "}
              <Link href="/my-subscription" className="text-blue-600 hover:underline font-semibold">
                Manage your subscription →
              </Link>
            </p>
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="max-w-3xl mx-auto px-6 py-16">
        <h2 className="text-2xl font-bold text-slate-900 mb-8 text-center">Pricing FAQ</h2>
        <div className="space-y-4">
          {[
            {
              q: "What's included in every lead?",
              a: "Every lead includes business name, phone number, address, and website (where available). Many leads also include Yelp ratings, review counts, and an AI conversion score. Email addresses are included where our enrichment has found them.",
            },
            {
              q: "How many times is each lead sold?",
              a: "We enforce a maximum of 5 sales per lead — hard-coded in the database. Once a lead hits 5 buyers, it's retired from the shop. Most competitors sell leads to unlimited buyers without disclosing this.",
            },
            {
              q: "How fresh is the data?",
              a: "All leads in our database were scraped within the last 180 days, and the vast majority were added within the last 30 days. We run scrapers 24/7 to keep adding new leads daily. If a lead is older than 180 days, it's automatically hidden from search results.",
            },
            {
              q: "What if I get a bad lead (disconnected number, wrong info)?",
              a: "Report it in your download confirmation email. We issue a store credit automatically — no questions asked.",
            },
            {
              q: "Can I buy the same industry/city every month to get new leads?",
              a: "Yes. As our scrapers add new leads daily, buying the same search next month will return a fresh batch. The download system automatically prioritizes leads you haven't purchased before.",
            },
            {
              q: "Do you cover industries outside contractors?",
              a: "Yes — we cover 93 industries including attorneys, dentists, accountants, financial advisors, photographers, event planners, auto repair, and more. If you have a specific niche, contact us.",
            },
          ].map((faq) => (
            <details key={faq.q} className="border border-slate-200 rounded-xl p-5 group">
              <summary className="font-semibold text-slate-900 cursor-pointer list-none flex justify-between items-center">
                {faq.q}
                <span className="text-slate-400 group-open:rotate-180 transition-transform text-sm">▼</span>
              </summary>
              <p className="mt-3 text-slate-600 text-sm leading-relaxed">{faq.a}</p>
            </details>
          ))}
        </div>
      </section>

      {/* Bottom CTA */}
      <div className="bg-blue-600 py-16">
        <div className="max-w-3xl mx-auto px-6 text-center text-white">
          <h2 className="text-3xl font-black mb-3">Ready to start? No commitment needed.</h2>
          <p className="text-blue-100 mb-8 text-lg">Browse leads, get 5 free samples, and only pay when you're ready.</p>
          <div className="flex gap-4 justify-center flex-wrap">
            <Link
              href="/shop"
              className="bg-white text-blue-600 hover:bg-blue-50 font-bold px-8 py-4 rounded-xl text-lg transition-all"
            >
              Browse Leads →
            </Link>
            <Link
              href="/subscribe"
              className="border border-blue-300 text-white hover:bg-blue-700 font-semibold px-8 py-4 rounded-xl text-lg transition-all"
            >
              View Subscription Plans
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
