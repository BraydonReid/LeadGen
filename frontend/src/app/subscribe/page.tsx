"use client";

import { useState } from "react";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { createSubscriptionCheckout } from "@/lib/api";

const PLANS = [
  {
    key: "starter",
    annualKey: "starter_annual",
    name: "Starter",
    price: "$29.99",
    annualPrice: "$299",
    annualSavings: "$61",
    leads: 50,
    perLead: "~$0.60/lead",
    annualPerLead: "~$0.50/lead",
    features: [
      "50 fresh leads every month",
      "Any industry + any state",
      "Instant CSV download, any time",
      "Cancel anytime",
    ],
  },
  {
    key: "pro",
    annualKey: "pro_annual",
    name: "Pro",
    price: "$99.99",
    annualPrice: "$999",
    annualSavings: "$201",
    leads: 300,
    perLead: "~$0.33/lead",
    annualPerLead: "~$0.28/lead",
    popular: true,
    features: [
      "300 fresh leads every month",
      "Any industry + any state",
      "Advanced Yelp & freshness filters",
      "AI conversion scores on all leads",
      "Instant CSV download, any time",
      "Cancel anytime",
    ],
  },
  {
    key: "agency",
    annualKey: "agency_annual",
    name: "Agency",
    price: "$299",
    annualPrice: "$2,990",
    annualSavings: "$598",
    leads: 1000,
    perLead: "~$0.30/lead",
    annualPerLead: "~$0.25/lead",
    badge: "Best Value",
    features: [
      "1,000 fresh leads every month",
      "Any industry + any state",
      "Advanced Yelp & freshness filters",
      "AI conversion scores on all leads",
      "Facebook & Instagram links included",
      "Instant CSV download, any time",
      "Cancel anytime",
    ],
  },
];

function SubscribeInner() {
  const searchParams = useSearchParams();
  const referralCode = searchParams.get("ref");
  const planParam = searchParams.get("plan");
  const [email, setEmail] = useState("");
  const [selectedPlan, setSelectedPlan] = useState(
    planParam === "starter" ? "starter" : planParam === "agency" ? "agency" : "pro"
  );
  const [billing, setBilling] = useState<"monthly" | "annual">("monthly");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!email.trim()) return;
    setLoading(true);
    try {
      const planKey = billing === "annual"
        ? (PLANS.find(p => p.key === selectedPlan)?.annualKey ?? selectedPlan)
        : selectedPlan;
      const { checkout_url } = await createSubscriptionCheckout(email.trim().toLowerCase(), referralCode ?? undefined, planKey);
      window.location.href = checkout_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-50 to-white flex items-center justify-center px-4 py-20">
      <div className="w-full max-w-2xl">
        {/* Header */}
        <div className="text-center mb-8">
          <span className="inline-block bg-blue-100 text-blue-700 text-xs font-bold tracking-widest uppercase px-4 py-1.5 rounded-full mb-4">
            Monthly Subscription
          </span>
          <h1 className="text-3xl font-black text-slate-900 mb-2">
            Fresh leads, every month.
          </h1>
          <p className="text-slate-500">
            Any industry. Any state. Cancel anytime.
          </p>
        </div>

        {/* Billing toggle */}
        <div className="flex items-center justify-center gap-3 mb-5">
          <button
            type="button"
            onClick={() => setBilling("monthly")}
            className={`text-sm font-semibold px-4 py-2 rounded-xl transition-all ${billing === "monthly" ? "bg-white shadow border border-slate-200 text-blue-600" : "text-slate-400 hover:text-slate-600"}`}
          >
            Monthly
          </button>
          <button
            type="button"
            onClick={() => setBilling("annual")}
            className={`text-sm font-semibold px-4 py-2 rounded-xl transition-all flex items-center gap-2 ${billing === "annual" ? "bg-white shadow border border-slate-200 text-blue-600" : "text-slate-400 hover:text-slate-600"}`}
          >
            Annual
            <span className="bg-emerald-100 text-emerald-700 text-xs font-bold px-2 py-0.5 rounded-full">
              2 months free
            </span>
          </button>
        </div>

        {/* Plan selector */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
          {PLANS.map((plan) => (
            <button
              key={plan.key}
              type="button"
              onClick={() => setSelectedPlan(plan.key)}
              className={`relative rounded-2xl border-2 p-6 text-left transition-all ${
                selectedPlan === plan.key
                  ? "border-blue-500 bg-white shadow-xl"
                  : "border-slate-200 bg-white hover:border-slate-300"
              }`}
            >
              {plan.popular && (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 bg-blue-500 text-white text-xs font-bold px-3 py-1 rounded-full whitespace-nowrap">
                  Most Popular
                </span>
              )}
              {"badge" in plan && plan.badge && (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 bg-violet-600 text-white text-xs font-bold px-3 py-1 rounded-full whitespace-nowrap">
                  {plan.badge}
                </span>
              )}
              <div className="flex items-center gap-2 mb-3">
                <div className={`w-4 h-4 rounded-full border-2 flex-shrink-0 ${
                  selectedPlan === plan.key ? "border-blue-500 bg-blue-500" : "border-slate-300"
                }`}>
                  {selectedPlan === plan.key && (
                    <div className="w-full h-full rounded-full bg-white scale-50 block" />
                  )}
                </div>
                <span className="font-bold text-slate-900">{plan.name}</span>
              </div>
              <div className="flex items-baseline gap-1 mb-1">
                <span className="text-3xl font-black text-slate-900">
                  {billing === "annual" ? plan.annualPrice : plan.price}
                </span>
                <span className="text-slate-400 text-sm">{billing === "annual" ? "/yr" : "/mo"}</span>
              </div>
              <div className="text-blue-600 font-semibold text-sm mb-1">{plan.leads} leads/month</div>
              <div className="text-slate-400 text-xs mb-1">
                {billing === "annual" ? plan.annualPerLead : plan.perLead} · billed {billing === "annual" ? "annually" : "monthly"}
              </div>
              {billing === "annual" && (
                <div className="text-emerald-600 text-xs font-semibold mb-3">Save {plan.annualSavings}/year</div>
              )}
              <ul className="space-y-1.5">
                {plan.features.map((f) => (
                  <li key={f} className="flex items-start gap-2 text-xs text-slate-600">
                    <svg className="w-3.5 h-3.5 text-emerald-500 mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                    </svg>
                    {f}
                  </li>
                ))}
              </ul>
            </button>
          ))}
        </div>

        {/* Email form */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
          <form onSubmit={handleSubmit} className="space-y-3">
            <input
              type="email"
              required
              placeholder="your@email.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={loading}
              className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
            />

            {error && (
              <p className="text-red-600 text-sm bg-red-50 rounded-xl px-4 py-2">{error}</p>
            )}

            <button
              type="submit"
              disabled={loading || !email.trim()}
              className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-bold py-3.5 rounded-xl text-base transition-all"
            >
              {loading
                ? "Redirecting to checkout…"
                : (() => {
                    const plan = PLANS.find(p => p.key === selectedPlan);
                    const price = billing === "annual" ? plan?.annualPrice : plan?.price;
                    const period = billing === "annual" ? "/yr" : "/mo";
                    return `Subscribe to ${plan?.name} — ${price}${period} →`;
                  })()}
            </button>
          </form>

          <p className="text-xs text-slate-400 mt-3 text-center">
            Powered by Stripe. No card stored here.
          </p>
        </div>

        {referralCode && (
          <div className="mt-4 bg-emerald-50 border border-emerald-200 rounded-xl px-4 py-3 text-center">
            <p className="text-emerald-700 text-sm font-semibold">
              Referral code applied — you&apos;ll get 50 bonus credits on sign-up!
            </p>
          </div>
        )}

        <p className="text-center text-sm text-slate-500 mt-4">
          Already subscribed?{" "}
          <a href="/my-subscription" className="text-blue-600 hover:underline font-semibold">
            Manage your subscription →
          </a>
        </p>
      </div>
    </div>
  );
}

export default function SubscribePage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-gradient-to-b from-blue-50 to-white" />}>
      <SubscribeInner />
    </Suspense>
  );
}
