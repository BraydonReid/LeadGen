"use client";

import { createCheckout, validatePromoCode } from "@/lib/api";
import { getUTM } from "@/lib/utm";
import { BULK_DISCOUNTS, calcTotal } from "@/types";
import { useEffect, useState } from "react";

interface Props {
  totalCount: number;
  avgLeadPrice: number;
  industry: string;
  state: string;
  city?: string;
  leadType?: string;
  zipCode?: string;
  radiusMiles?: number;
}

export default function PriceCalculator({ totalCount, avgLeadPrice, industry, state, city, leadType, zipCode, radiusMiles }: Props) {
  const maxQty = Math.min(totalCount, 10000);
  const [quantity, setQuantity] = useState(Math.min(100, maxQty));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [promoCode, setPromoCode] = useState("");
  const [promoApplied, setPromoApplied] = useState(false);
  const [creditDiscountDollars, setCreditDiscountDollars] = useState(0);

  const { discountPct, subtotal, total: baseTotal, perLead } = calcTotal(avgLeadPrice, quantity);
  const total = Math.max(0.5, baseTotal - creditDiscountDollars);

  useEffect(() => {
    setQuantity(Math.min(100, maxQty));
  }, [maxQty]);

  const handleBuy = async () => {
    setLoading(true);
    setError(null);
    try {
      const utm = getUTM();
      const res = await createCheckout({
        industry, state, city, quantity,
        lead_type: leadType,
        zip_code: zipCode,
        radius_miles: radiusMiles,
        promo_code: promoApplied ? promoCode.trim().toUpperCase() : undefined,
        ...utm,
      });
      window.location.href = res.checkout_url;
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Something went wrong");
      setLoading(false);
    }
  };

  const [promoLoading, setPromoLoading] = useState(false);

  const handleApplyPromo = async () => {
    const code = promoCode.trim().toUpperCase();
    if (!code) return;
    setError(null);
    setPromoLoading(true);
    try {
      const result = await validatePromoCode(code);
      setCreditDiscountDollars(result.discount_dollars);
      setPromoApplied(true);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Invalid promo code");
      setPromoApplied(false);
      setCreditDiscountDollars(0);
    } finally {
      setPromoLoading(false);
    }
  };

  const handleRemovePromo = () => {
    setPromoApplied(false);
    setPromoCode("");
    setCreditDiscountDollars(0);
    setError(null);
  };

  const activeTier = BULK_DISCOUNTS.find((t) => quantity >= t.min);

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden sticky top-6">
      {/* Header */}
      <div className="bg-slate-900 text-white px-6 py-5">
        <div className="text-sm text-slate-400 mb-1">Price Calculator</div>
        <div className="text-3xl font-black">${total.toFixed(2)}</div>
        <div className="text-sm text-slate-400 mt-1">
          for {quantity.toLocaleString()} leads
        </div>
      </div>

      <div className="p-6 space-y-6">
        {/* Quantity input */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <label className="text-sm font-semibold text-slate-700">Quantity</label>
            <div className="flex items-center gap-2">
              <input
                type="number"
                min={1}
                max={maxQty}
                value={quantity}
                onChange={(e) => {
                  const v = Math.max(1, Math.min(maxQty, Number(e.target.value) || 1));
                  setQuantity(v);
                }}
                className="w-24 border border-slate-200 rounded-lg px-3 py-1.5 text-sm text-right font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <span className="text-xs text-slate-400">/ {maxQty.toLocaleString()} max</span>
            </div>
          </div>
          <input
            type="range"
            min={1}
            max={maxQty}
            value={quantity}
            onChange={(e) => setQuantity(Number(e.target.value))}
            className="w-full accent-blue-600"
          />
          <div className="flex justify-between text-xs text-slate-400 mt-1">
            <span>1</span>
            <span>{maxQty.toLocaleString()}</span>
          </div>
        </div>

        {/* Bulk discount tiers */}
        <div>
          <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Bulk Discounts</div>
          <div className="space-y-1">
            {BULK_DISCOUNTS.filter((t) => t.discount > 0).map((tier) => (
              <div
                key={tier.min}
                className={`flex justify-between text-sm px-3 py-1.5 rounded-lg transition-colors ${
                  activeTier?.min === tier.min
                    ? "bg-blue-50 text-blue-700 font-semibold"
                    : "text-slate-500"
                }`}
              >
                <span>{tier.min.toLocaleString()}+ leads</span>
                <span>{Math.round(tier.discount * 100)}% off</span>
              </div>
            ))}
          </div>
        </div>

        {/* Price breakdown */}
        <div className="bg-slate-50 rounded-xl p-4 space-y-2 text-sm">
          <div className="flex justify-between text-slate-600">
            <span>Avg price per lead</span>
            <span>${perLead.toFixed(3)}</span>
          </div>
          <div className="flex justify-between text-slate-600">
            <span>Subtotal ({quantity.toLocaleString()} × ${avgLeadPrice.toFixed(3)})</span>
            <span>${subtotal.toFixed(2)}</span>
          </div>
          {discountPct > 0 && (
            <div className="flex justify-between text-emerald-600 font-medium">
              <span>Bulk discount ({discountPct}% off)</span>
              <span>−${(subtotal - baseTotal).toFixed(2)}</span>
            </div>
          )}
          {promoApplied && creditDiscountDollars > 0 && (
            <div className="flex justify-between text-emerald-600 font-medium">
              <span>Promo code ({promoCode.trim().toUpperCase()})</span>
              <span>−${creditDiscountDollars.toFixed(2)}</span>
            </div>
          )}
          <div className="flex justify-between font-bold text-slate-900 pt-2 border-t border-slate-200 text-base">
            <span>Total</span>
            <span>${total.toFixed(2)}</span>
          </div>
        </div>

        {/* Promo code */}
        <div>
          {!promoApplied ? (
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Promo / credit code"
                value={promoCode}
                onChange={(e) => setPromoCode(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleApplyPromo()}
                className="flex-1 border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 uppercase placeholder:normal-case"
              />
              <button
                onClick={handleApplyPromo}
                disabled={promoLoading || !promoCode.trim()}
                className="text-sm bg-slate-800 hover:bg-slate-900 disabled:opacity-40 text-white px-4 py-2 rounded-lg transition-colors"
              >
                {promoLoading ? "…" : "Apply"}
              </button>
            </div>
          ) : (
            <div className="flex items-center justify-between bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2">
              <span className="text-sm text-emerald-700 font-medium">
                {promoCode.trim().toUpperCase()} applied — −${creditDiscountDollars.toFixed(2)}
              </span>
              <button onClick={handleRemovePromo} className="text-xs text-emerald-500 hover:text-emerald-700 ml-2">
                Remove
              </button>
            </div>
          )}
        </div>

        {error && (
          <div className="bg-red-50 text-red-600 text-sm p-3 rounded-lg">{error}</div>
        )}

        <button
          onClick={handleBuy}
          disabled={loading || totalCount === 0}
          className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-bold py-4 rounded-xl text-lg transition-all hover:scale-[1.02] shadow-md shadow-blue-500/20"
        >
          {loading ? "Redirecting to checkout…" : `Buy ${quantity.toLocaleString()} Leads — $${total.toFixed(2)}${promoApplied ? " ✓" : ""}`}
        </button>

        <p className="text-xs text-slate-400 text-center">
          Secure checkout via Stripe. Instant CSV download after payment.
        </p>
      </div>
    </div>
  );
}
