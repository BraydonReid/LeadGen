"use client";

import { createCheckout } from "@/lib/api";
import { useState } from "react";

const TIERS = [
  { quantity: 100, price: 9, label: "Starter" },
  { quantity: 500, price: 29, label: "Growth", popular: true },
  { quantity: 1000, price: 49, label: "Pro" },
];

interface Props {
  industry: string;
  state: string;
  city?: string;
  totalCount: number;
}

export default function PricingTiers({ industry, state, city, totalCount }: Props) {
  const [loading, setLoading] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleBuy = async (quantity: number) => {
    setLoading(quantity);
    setError(null);
    try {
      const { checkout_url } = await createCheckout({ industry, state, city, quantity });
      window.location.href = checkout_url;
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Something went wrong");
      setLoading(null);
    }
  };

  return (
    <div>
      <h2 className="text-xl font-bold mb-2">Download your leads</h2>
      <p className="text-gray-500 text-sm mb-6">
        {totalCount.toLocaleString()} leads available. Purchase to get the full CSV with email,
        phone, and website.
      </p>

      {error && (
        <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm">{error}</div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {TIERS.map(({ quantity, price, label, popular }) => {
          const available = Math.min(quantity, totalCount);
          const disabled = totalCount === 0 || loading !== null;

          return (
            <div
              key={quantity}
              className={`relative rounded-xl border-2 p-6 ${
                popular ? "border-blue-500 shadow-md" : "border-gray-200"
              }`}
            >
              {popular && (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 bg-blue-500 text-white text-xs font-bold px-3 py-1 rounded-full">
                  Most Popular
                </span>
              )}
              <div className="text-lg font-bold mb-1">{label}</div>
              <div className="text-3xl font-extrabold mb-1">
                ${price}
              </div>
              <div className="text-sm text-gray-500 mb-4">
                {available.toLocaleString()} leads
                {available < quantity && (
                  <span className="ml-1 text-orange-500">(all available)</span>
                )}
              </div>
              <ul className="text-xs text-gray-600 space-y-1 mb-5">
                <li>Business name, city, state</li>
                <li>Phone number</li>
                <li>Email address</li>
                <li>Website URL</li>
                <li>Instant CSV download</li>
              </ul>
              <button
                onClick={() => handleBuy(quantity)}
                disabled={disabled || available === 0}
                className={`w-full py-2.5 rounded-lg font-semibold text-sm transition ${
                  popular
                    ? "bg-blue-600 hover:bg-blue-700 text-white"
                    : "bg-gray-100 hover:bg-gray-200 text-gray-900"
                } disabled:opacity-50 disabled:cursor-not-allowed`}
              >
                {loading === quantity ? "Redirecting..." : `Buy ${quantity} leads — $${price}`}
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
