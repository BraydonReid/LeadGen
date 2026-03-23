"use client";

import { useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { createSubscriptionCheckout } from "@/lib/api";

function SubscribeInner() {
  const searchParams = useSearchParams();
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const referralCode = searchParams.get("ref");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!email.trim()) return;
    setLoading(true);
    try {
      const { checkout_url } = await createSubscriptionCheckout(email.trim().toLowerCase(), referralCode ?? undefined);
      window.location.href = checkout_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-50 to-white flex items-center justify-center px-4 py-20">
      <div className="w-full max-w-md">
        {/* Badge */}
        <div className="text-center mb-8">
          <span className="inline-block bg-blue-100 text-blue-700 text-xs font-bold tracking-widest uppercase px-4 py-1.5 rounded-full mb-4">
            Pro Subscription
          </span>
          <h1 className="text-3xl font-black text-slate-900 mb-2">
            300 fresh leads, every month.
          </h1>
          <p className="text-slate-500">
            Any industry. Any state. Cancel anytime.
          </p>
        </div>

        {/* Plan card */}
        <div className="bg-white rounded-2xl border-2 border-blue-500 shadow-xl p-8 mb-6">
          <div className="flex items-baseline gap-1 mb-1">
            <span className="text-5xl font-black text-slate-900">$99</span>
            <span className="text-slate-400 text-sm">/month</span>
          </div>
          <div className="text-blue-600 font-semibold mb-1">300 leads/month</div>
          <div className="text-slate-400 text-xs mb-6">~$0.33 per lead · billed monthly</div>

          <ul className="space-y-2.5 mb-8">
            {[
              "300 fresh leads every month",
              "Any industry + any state",
              "Advanced Yelp & freshness filters",
              "AI conversion scores on all leads",
              "Instant CSV download, any time",
              "Cancel from your dashboard anytime",
            ].map((f) => (
              <li key={f} className="flex items-start gap-2 text-sm text-slate-700">
                <svg className="w-4 h-4 text-emerald-500 mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                </svg>
                {f}
              </li>
            ))}
          </ul>

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
              {loading ? "Redirecting to checkout…" : "Subscribe Now →"}
            </button>
          </form>

          <p className="text-xs text-slate-400 mt-3 text-center">
            Powered by Stripe. No card stored here.
          </p>
        </div>

        {referralCode && (
          <div className="bg-emerald-50 border border-emerald-200 rounded-xl px-4 py-3 text-center">
            <p className="text-emerald-700 text-sm font-semibold">
              Referral code applied — you&apos;ll get 50 bonus credits on sign-up!
            </p>
          </div>
        )}

        {/* Already subscribed link */}
        <p className="text-center text-sm text-slate-500">
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
