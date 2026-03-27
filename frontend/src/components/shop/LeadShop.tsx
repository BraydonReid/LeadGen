"use client";

import { aiSearch, getOrders, requestFreeSample, shopSearch, type ShopFilters } from "@/lib/api";
import type { AISearchIntent, OrderSummary, ShopResponse } from "@/types";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import AISearchBar from "./AISearchBar";
import PriceCalculator from "./PriceCalculator";

const US_STATES = [
  ["AL","Alabama"],["AK","Alaska"],["AZ","Arizona"],["AR","Arkansas"],
  ["CA","California"],["CO","Colorado"],["CT","Connecticut"],["DE","Delaware"],
  ["FL","Florida"],["GA","Georgia"],["HI","Hawaii"],["ID","Idaho"],
  ["IL","Illinois"],["IN","Indiana"],["IA","Iowa"],["KS","Kansas"],
  ["KY","Kentucky"],["LA","Louisiana"],["ME","Maine"],["MD","Maryland"],
  ["MA","Massachusetts"],["MI","Michigan"],["MN","Minnesota"],["MS","Mississippi"],
  ["MO","Missouri"],["MT","Montana"],["NE","Nebraska"],["NV","Nevada"],
  ["NH","New Hampshire"],["NJ","New Jersey"],["NM","New Mexico"],["NY","New York"],
  ["NC","North Carolina"],["ND","North Dakota"],["OH","Ohio"],["OK","Oklahoma"],
  ["OR","Oregon"],["PA","Pennsylvania"],["RI","Rhode Island"],["SC","South Carolina"],
  ["SD","South Dakota"],["TN","Tennessee"],["TX","Texas"],["UT","Utah"],
  ["VT","Vermont"],["VA","Virginia"],["WA","Washington"],["WV","West Virginia"],
  ["WI","Wisconsin"],["WY","Wyoming"],
];

const RADIUS_OPTIONS = [5, 10, 25, 50, 100];

export default function LeadShop() {
  const searchParams = useSearchParams();
  const router = useRouter();

  const [industry, setIndustry] = useState(searchParams.get("industry") ?? "");
  const [state, setState] = useState(searchParams.get("state") ?? "");
  const [city, setCity] = useState(searchParams.get("city") ?? "");
  const [leadType, setLeadType] = useState(searchParams.get("lead_type") ?? "all");
  const [zipCode, setZipCode] = useState(searchParams.get("zip_code") ?? "");
  const [radiusMiles, setRadiusMiles] = useState<number>(
    Number(searchParams.get("radius_miles")) || 25
  );
  const [useRadius, setUseRadius] = useState(!!searchParams.get("zip_code"));

  const [results, setResults] = useState<ShopResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);

  // Advanced filters
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [hasYelp, setHasYelp] = useState(false);
  const [yelpMode, setYelpMode] = useState<"any" | "high" | "struggling">("any");
  const [addedDays, setAddedDays] = useState<number | undefined>(undefined);
  const [hasEmail, setHasEmail] = useState(false);
  const [hasContact, setHasContact] = useState(false);
  const [hasAddress, setHasAddress] = useState(false);
  const [minConversion, setMinConversion] = useState<number | undefined>(undefined);

  const getFilters = (): ShopFilters => ({
    hasYelp: hasYelp || yelpMode !== "any" || undefined,
    yelpMin: yelpMode === "high" ? 4.0 : undefined,
    yelpMax: yelpMode === "struggling" ? 3.0 : undefined,
    addedDays: addedDays,
    hasEmail: hasEmail || undefined,
    hasContact: hasContact || undefined,
    hasAddress: hasAddress || undefined,
    minConversion: minConversion,
  });

  // AI search mode
  const [searchMode, setSearchMode] = useState<"standard" | "ai">("standard");
  const [aiIntent, setAiIntent] = useState<AISearchIntent | null>(null);

  // Free sample state
  const [sampleEmail, setSampleEmail] = useState("");
  const [sampleLoading, setSampleLoading] = useState(false);
  const [sampleDone, setSampleDone] = useState(false);
  const [sampleError, setSampleError] = useState<string | null>(null);

  // Request industry modal
  const [showRequestModal, setShowRequestModal] = useState(false);
  const [requestEmail, setRequestEmail] = useState("");
  const [requestLoading, setRequestLoading] = useState(false);
  const [requestDone, setRequestDone] = useState(false);
  const [requestError, setRequestError] = useState<string | null>(null);

  // Order history — email-based, no account needed
  const [buyerEmail, setBuyerEmail] = useState("");
  const [emailInputVisible, setEmailInputVisible] = useState(false);
  const [emailDraft, setEmailDraft] = useState("");
  const [orders, setOrders] = useState<OrderSummary[]>([]);
  const [ordersLoading, setOrdersLoading] = useState(false);

  // Load saved email from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem("buyerEmail");
    if (saved) {
      setBuyerEmail(saved);
      fetchOrders(saved);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchOrders = async (email: string) => {
    setOrdersLoading(true);
    try {
      const data = await getOrders(email);
      setOrders(data.purchases);
    } finally {
      setOrdersLoading(false);
    }
  };

  const handleSetEmail = (e: React.FormEvent) => {
    e.preventDefault();
    const email = emailDraft.trim().toLowerCase();
    if (!email) return;
    setBuyerEmail(email);
    localStorage.setItem("buyerEmail", email);
    setEmailInputVisible(false);
    fetchOrders(email);
  };

  const handleClearEmail = () => {
    setBuyerEmail("");
    setEmailDraft("");
    setOrders([]);
    localStorage.removeItem("buyerEmail");
  };

  // Check if current results match a previously purchased search
  const duplicatePurchase = results && orders.find((o) =>
    o.industry.toLowerCase() === results.query.industry.toLowerCase() &&
    o.state.toUpperCase() === results.query.state.toUpperCase()
  );

  const doSearch = async (
    ind: string,
    st: string,
    ct: string,
    lt: string,
    zip: string,
    radius: number,
    withRadius: boolean,
  ) => {
    if (!ind.trim()) return;
    if (!st && !zip) return;
    setLoading(true);
    setError(null);
    setSearched(true);
    setSampleDone(false);
    setSampleError(null);
    try {
      const data = await shopSearch(
        ind.trim(),
        st,
        ct.trim() || undefined,
        lt === "all" ? undefined : lt,
        withRadius && zip ? zip : undefined,
        withRadius && zip ? radius : undefined,
        getFilters(),
      );
      setResults(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Search failed");
      setResults(null);
    } finally {
      setLoading(false);
    }
  };

  const doAiSearch = async (query: string) => {
    setLoading(true);
    setError(null);
    setSearched(true);
    setAiIntent(null);
    setSampleDone(false);
    setSampleError(null);
    try {
      const data = await aiSearch(query);
      setAiIntent(data.intent);
      // Normalize AI response to ShopResponse shape so PriceCalculator works unchanged
      setResults({
        total_count: data.total_count,
        avg_lead_price: data.avg_lead_price,
        preview: data.preview,
        query: data.query,
      });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "AI search failed";
      if (msg.includes("temporarily unavailable")) {
        setError("AI search is warming up — try again in a moment, or use Standard Search below.");
      } else {
        setError(msg);
      }
      setResults(null);
    } finally {
      setLoading(false);
    }
  };

  // Auto-search if URL has params
  useEffect(() => {
    const ind = searchParams.get("industry") ?? "";
    const st = searchParams.get("state") ?? "";
    const ct = searchParams.get("city") ?? "";
    const lt = searchParams.get("lead_type") ?? "all";
    const zip = searchParams.get("zip_code") ?? "";
    const radius = Number(searchParams.get("radius_miles")) || 25;
    const withRadius = !!zip;
    if (ind && (st || zip)) {
      setIndustry(ind); setState(st); setCity(ct); setLeadType(lt);
      setZipCode(zip); setRadiusMiles(radius); setUseRadius(withRadius);
      doSearch(ind, st, ct, lt, zip, radius, withRadius);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const params = new URLSearchParams({ industry: industry.trim() });
    if (state) params.set("state", state);
    if (city.trim()) params.set("city", city.trim());
    if (leadType !== "all") params.set("lead_type", leadType);
    if (useRadius && zipCode.trim()) {
      params.set("zip_code", zipCode.trim());
      params.set("radius_miles", String(radiusMiles));
    }
    router.push(`/shop?${params}`, { scroll: false });
    doSearch(industry, state, city, leadType, zipCode, radiusMiles, useRadius);
  };

  const query = results?.query;

  const handleGetSample = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!results || !sampleEmail.trim()) return;
    setSampleLoading(true);
    setSampleError(null);
    try {
      const blob = await requestFreeSample({
        email: sampleEmail.trim(),
        industry: results.query.industry,
        state: results.query.state,
        city: results.query.city ?? undefined,
        lead_type: results.query.lead_type ?? undefined,
        zip_code: results.query.zip_code ?? undefined,
        radius_miles: results.query.radius_miles ?? undefined,
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `sample-${results.query.industry.toLowerCase().replace(/\s+/g, "-")}-leads.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      setSampleDone(true);
    } catch (e: unknown) {
      setSampleError(e instanceof Error ? e.message : "Sample request failed");
    } finally {
      setSampleLoading(false);
    }
  };

  return (
    <div>
      {/* Search bar */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 mb-8">
        {/* Search mode toggle */}
        <div className="flex items-center gap-1 bg-slate-100 rounded-xl p-1 w-fit mb-5">
          <button
            type="button"
            onClick={() => { setSearchMode("standard"); setAiIntent(null); }}
            className={`text-xs font-semibold px-3 py-1.5 rounded-lg transition-all ${
              searchMode === "standard" ? "bg-white shadow text-blue-600" : "text-slate-500 hover:text-slate-700"
            }`}
          >
            Standard Search
          </button>
          <button
            type="button"
            onClick={() => setSearchMode("ai")}
            className={`text-xs font-semibold px-3 py-1.5 rounded-lg transition-all flex items-center gap-1 ${
              searchMode === "ai" ? "bg-violet-600 text-white shadow" : "text-slate-500 hover:text-slate-700"
            }`}
          >
            <span>✦</span> AI Search
          </button>
        </div>

        {/* AI Search mode */}
        {searchMode === "ai" && (
          <AISearchBar
            onSearch={doAiSearch}
            loading={loading}
            naturalExplanation={aiIntent?.natural_explanation}
          />
        )}

        {/* Standard search form */}
        {searchMode === "standard" && (
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="flex flex-col sm:flex-row gap-3">
            <input
              type="text"
              placeholder="Industry (e.g. roofing, plumbing, solar…)"
              value={industry}
              onChange={(e) => setIndustry(e.target.value)}
              className="flex-1 border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              required
            />
            {!useRadius && (
              <select
                value={state}
                onChange={(e) => setState(e.target.value)}
                className="w-full sm:w-44 border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                required={!useRadius}
              >
                <option value="">State…</option>
                {US_STATES.map(([code, name]) => (
                  <option key={code} value={code}>{name} ({code})</option>
                ))}
              </select>
            )}
            {!useRadius && (
              <input
                type="text"
                placeholder="City (optional)"
                value={city}
                onChange={(e) => setCity(e.target.value)}
                className="w-full sm:w-36 border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            )}
            {useRadius && (
              <>
                <input
                  type="text"
                  placeholder="ZIP code"
                  value={zipCode}
                  onChange={(e) => setZipCode(e.target.value)}
                  maxLength={5}
                  className="w-full sm:w-32 border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  required={useRadius}
                />
                <select
                  value={radiusMiles}
                  onChange={(e) => setRadiusMiles(Number(e.target.value))}
                  className="w-full sm:w-36 border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {RADIUS_OPTIONS.map((r) => (
                    <option key={r} value={r}>{r} mi radius</option>
                  ))}
                </select>
              </>
            )}
            <button
              type="submit"
              disabled={loading}
              className="bg-blue-600 hover:bg-blue-700 text-white font-bold px-6 py-3 rounded-xl text-sm transition-all disabled:opacity-50 whitespace-nowrap"
            >
              {loading ? "Searching…" : "Search Leads"}
            </button>
          </div>

          {/* Advanced filters toggle */}
          <div>
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="text-xs text-slate-400 hover:text-blue-600 transition-colors flex items-center gap-1"
            >
              <span>{showAdvanced ? "▾" : "▸"}</span> Advanced filters
              {(hasYelp || yelpMode !== "any" || addedDays || hasEmail || hasContact || hasAddress || minConversion != null) && (
                <span className="ml-1 bg-blue-100 text-blue-700 text-xs font-bold px-1.5 py-0.5 rounded-full">
                  {[hasYelp || yelpMode !== "any", !!addedDays, hasEmail, hasContact, hasAddress, minConversion != null].filter(Boolean).length} active
                </span>
              )}
            </button>
            {showAdvanced && (
              <div className="mt-3 p-4 bg-slate-50 rounded-xl border border-slate-200 space-y-4">
                {/* Freshness */}
                <div>
                  <p className="text-xs font-semibold text-slate-600 mb-2">Lead Freshness</p>
                  <div className="flex flex-wrap gap-2">
                    {[
                      { label: "Any time", value: undefined },
                      { label: "Last 7 days", value: 7 },
                      { label: "Last 30 days", value: 30 },
                      { label: "Last 90 days", value: 90 },
                    ].map(({ label, value }) => (
                      <button
                        key={label}
                        type="button"
                        onClick={() => setAddedDays(value)}
                        className={`text-xs px-3 py-1.5 rounded-lg font-semibold transition-all ${
                          addedDays === value
                            ? "bg-blue-600 text-white"
                            : "bg-white border border-slate-200 text-slate-600 hover:border-blue-300"
                        }`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Yelp/Reputation */}
                <div>
                  <p className="text-xs font-semibold text-slate-600 mb-1">Yelp Reputation</p>
                  <p className="text-xs text-slate-400 mb-2">
                    Target businesses by their online reputation — great for sales outreach strategy.
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {[
                      { label: "Any", value: "any", desc: "" },
                      { label: "⭐ Yelp Rated (any)", value: "has_yelp", desc: "Has Yelp profile" },
                      { label: "⭐⭐⭐⭐ Top Rated (4.0+)", value: "high", desc: "Established, growing businesses" },
                      { label: "⚠ Struggling (≤3.0)", value: "struggling", desc: "Businesses that need help — best for agencies" },
                    ].map(({ label, value }) => (
                      <button
                        key={value}
                        type="button"
                        onClick={() => {
                          if (value === "has_yelp") { setHasYelp(true); setYelpMode("any"); }
                          else if (value === "any") { setHasYelp(false); setYelpMode("any"); }
                          else { setHasYelp(false); setYelpMode(value as "high" | "struggling"); }
                        }}
                        className={`text-xs px-3 py-1.5 rounded-lg font-semibold transition-all ${
                          (value === "any" && !hasYelp && yelpMode === "any") ||
                          (value === "has_yelp" && hasYelp) ||
                          ((value as string) === yelpMode && value !== "any" && value !== "has_yelp")
                            ? value === "struggling"
                              ? "bg-amber-500 text-white"
                              : "bg-blue-600 text-white"
                            : "bg-white border border-slate-200 text-slate-600 hover:border-blue-300"
                        }`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                  {yelpMode === "struggling" && (
                    <p className="text-xs text-amber-600 mt-2 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                      Struggling businesses (≤3.0 Yelp) are ideal leads for marketing agencies, reputation management, and CRM vendors. They know they have a problem and are actively looking for solutions.
                    </p>
                  )}
                </div>

                {/* Contact data completeness */}
                <div>
                  <p className="text-xs font-semibold text-slate-600 mb-1">Contact Data</p>
                  <p className="text-xs text-slate-400 mb-2">Filter to leads with verified contact information already in the CSV.</p>
                  <div className="flex flex-wrap gap-2">
                    {[
                      { label: "Has Email", state: hasEmail, setter: setHasEmail },
                      { label: "Has Contact Name", state: hasContact, setter: setHasContact },
                      { label: "Has Street Address", state: hasAddress, setter: setHasAddress },
                    ].map(({ label, state: active, setter }) => (
                      <button
                        key={label}
                        type="button"
                        onClick={() => setter(!active)}
                        className={`text-xs px-3 py-1.5 rounded-lg font-semibold transition-all ${
                          active
                            ? "bg-emerald-600 text-white"
                            : "bg-white border border-slate-200 text-slate-600 hover:border-emerald-300"
                        }`}
                      >
                        {active ? "✓ " : ""}{label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* AI Score filter */}
                <div>
                  <p className="text-xs font-semibold text-slate-600 mb-1">Min AI Conversion Score</p>
                  <p className="text-xs text-slate-400 mb-2">Only show leads above a certain AI quality score (0–100).</p>
                  <div className="flex flex-wrap gap-2">
                    {[
                      { label: "Any", value: undefined },
                      { label: "50+", value: 50 },
                      { label: "65+", value: 65 },
                      { label: "75+", value: 75 },
                    ].map(({ label, value }) => (
                      <button
                        key={label}
                        type="button"
                        onClick={() => setMinConversion(value)}
                        className={`text-xs px-3 py-1.5 rounded-lg font-semibold transition-all ${
                          minConversion === value
                            ? "bg-blue-600 text-white"
                            : "bg-white border border-slate-200 text-slate-600 hover:border-blue-300"
                        }`}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Search mode + lead type toggles */}
          <div className="flex flex-wrap items-center gap-4">
            {/* Radius toggle */}
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => { setUseRadius(false); setZipCode(""); }}
                className={`text-xs font-semibold px-3 py-1.5 rounded-lg transition-all whitespace-nowrap ${
                  !useRadius ? "bg-white shadow text-blue-600 border border-slate-200" : "text-slate-500 hover:text-slate-700"
                }`}
              >
                City / State
              </button>
              <button
                type="button"
                onClick={() => { setUseRadius(true); setState(""); setCity(""); }}
                className={`text-xs font-semibold px-3 py-1.5 rounded-lg transition-all whitespace-nowrap ${
                  useRadius ? "bg-white shadow text-blue-600 border border-slate-200" : "text-slate-500 hover:text-slate-700"
                }`}
              >
                ZIP + Radius
              </button>
            </div>

            <div className="h-4 w-px bg-slate-200 hidden sm:block" />

            {/* Lead type toggle */}
            <div className="flex items-center gap-3">
              <span className="text-xs font-semibold text-slate-500 whitespace-nowrap">Lead Type:</span>
              <div className="flex items-center gap-1 bg-slate-100 rounded-xl p-1">
                {[
                  { value: "all", label: "All Leads" },
                  { value: "business", label: "Business Directory" },
                  { value: "consumer", label: "Intent Leads" },
                ].map(({ value, label }) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setLeadType(value)}
                    className={`text-xs font-semibold px-3 py-1.5 rounded-lg transition-all whitespace-nowrap ${
                      leadType === value
                        ? value === "consumer"
                          ? "bg-teal-600 text-white shadow"
                          : "bg-white shadow text-blue-600"
                        : "text-slate-500 hover:text-slate-700"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </form>
        )}

        {/* Request industry link */}
        <div className="mt-3 pt-3 border-t border-slate-100 text-center">
          <button
            type="button"
            onClick={() => { setShowRequestModal(true); setRequestDone(false); setRequestError(null); }}
            className="text-xs text-slate-400 hover:text-blue-600 transition-colors"
          >
            Don&apos;t see your industry? Request it and we&apos;ll add it →
          </button>
        </div>
      </div>

      {/* Order history — email-based */}
      <div className="mb-6">
        {!buyerEmail ? (
          <div className="flex items-center gap-3">
            {!emailInputVisible ? (
              <button
                type="button"
                onClick={() => setEmailInputVisible(true)}
                className="text-xs text-slate-400 hover:text-blue-600 transition-colors"
              >
                Already a customer? Enter your email to see past orders →
              </button>
            ) : (
              <form onSubmit={handleSetEmail} className="flex items-center gap-2">
                <input
                  type="email"
                  required
                  autoFocus
                  placeholder="your@email.com"
                  value={emailDraft}
                  onChange={(e) => setEmailDraft(e.target.value)}
                  className="border border-slate-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 w-64"
                />
                <button
                  type="submit"
                  className="bg-blue-600 text-white text-xs font-semibold px-3 py-1.5 rounded-lg hover:bg-blue-700 transition-colors"
                >
                  Look up orders
                </button>
                <button
                  type="button"
                  onClick={() => setEmailInputVisible(false)}
                  className="text-slate-400 hover:text-slate-600 text-xs"
                >
                  Cancel
                </button>
              </form>
            )}
          </div>
        ) : (
          <div>
            <div className="flex items-center gap-3 mb-2">
              <span className="text-xs text-slate-500">
                Showing orders for <span className="font-semibold text-slate-700">{buyerEmail}</span>
              </span>
              <button
                type="button"
                onClick={handleClearEmail}
                className="text-xs text-slate-400 hover:text-red-500 transition-colors"
              >
                Clear
              </button>
            </div>
            {ordersLoading && (
              <p className="text-xs text-slate-400">Loading order history…</p>
            )}
            {!ordersLoading && orders.length === 0 && (
              <p className="text-xs text-slate-400">No purchases found for this email.</p>
            )}
            {!ordersLoading && orders.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {orders.map((o) => (
                  <div
                    key={o.id}
                    className="flex items-center gap-2 bg-slate-100 rounded-full px-3 py-1.5 text-xs"
                  >
                    <span className="font-semibold text-slate-700">{o.quantity.toLocaleString()} {o.industry}</span>
                    <span className="text-slate-500">·</span>
                    <span className="text-slate-500">{o.city ? `${o.city}, ` : ""}{o.state}</span>
                    <span className="text-slate-400">·</span>
                    <span className="text-slate-400">
                      {new Date(o.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                    </span>
                    <a
                      href={`/success?session_id=${o.stripe_session_id}`}
                      className="text-blue-500 hover:text-blue-700 font-semibold ml-1"
                      title="Re-download"
                    >
                      ↓
                    </a>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Intent lead CTA — shown when not filtering for consumer */}
      {!searched && leadType !== "consumer" && (
        <div className="bg-teal-50 border border-teal-200 rounded-2xl p-5 mb-8 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <p className="text-sm font-bold text-teal-800">Looking for high-converting consumer intent leads?</p>
            <p className="text-xs text-teal-600 mt-0.5">
              Intent leads are submitted directly by homeowners actively seeking services — they convert 3–5× better than directory leads.
            </p>
          </div>
          <a
            href="/request-service"
            className="shrink-0 bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold px-4 py-2 rounded-lg transition-colors whitespace-nowrap"
          >
            Drive Intent Lead Volume →
          </a>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-50 text-red-700 p-4 rounded-xl mb-6 text-sm">{error}</div>
      )}

      {/* No results */}
      {searched && !loading && results && results.total_count === 0 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-2xl p-8 text-center">
          <div className="text-3xl mb-3">🔍</div>
          <h3 className="font-bold text-yellow-900 mb-1">No leads found</h3>
          <p className="text-yellow-700 text-sm mb-4">
            Try a different industry, expand your radius, or broaden your location. Our database grows daily.
          </p>
          <button
            type="button"
            onClick={() => { setShowRequestModal(true); setRequestDone(false); setRequestError(null); }}
            className="inline-block bg-yellow-600 hover:bg-yellow-700 text-white text-sm font-bold px-5 py-2.5 rounded-xl transition-all"
          >
            Request this industry — we&apos;ll notify you when leads arrive →
          </button>
        </div>
      )}

      {/* Request Industry Modal */}
      {showRequestModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={() => setShowRequestModal(false)}>
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm p-6" onClick={(e) => e.stopPropagation()}>
            {requestDone ? (
              <div className="text-center py-4">
                <div className="text-4xl mb-3">📬</div>
                <h3 className="text-lg font-black text-slate-900 mb-2">Request received!</h3>
                <p className="text-slate-500 text-sm mb-4">
                  We&apos;ll email you as soon as <strong>{industry || "this industry"}</strong> leads are available
                  {state ? ` in ${state}` : ""}.
                </p>
                <button onClick={() => setShowRequestModal(false)} className="text-blue-600 hover:underline text-sm font-semibold">
                  Close
                </button>
              </div>
            ) : (
              <>
                <h3 className="text-lg font-black text-slate-900 mb-1">Request this industry</h3>
                <p className="text-slate-500 text-sm mb-4">
                  Enter your email and we&apos;ll notify you when <strong>{industry || "this industry"}</strong> leads
                  {state ? ` in ${state}` : ""} become available. Usually within 1–2 weeks.
                </p>
                <form
                  onSubmit={async (e) => {
                    e.preventDefault();
                    setRequestLoading(true);
                    setRequestError(null);
                    try {
                      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/industry-request`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ email: requestEmail.trim().toLowerCase(), industry: industry || "general", state: state || "TX", city: city || null }),
                      });
                      if (!res.ok) throw new Error("Request failed");
                      setRequestDone(true);
                    } catch {
                      setRequestError("Something went wrong. Please try again.");
                    } finally {
                      setRequestLoading(false);
                    }
                  }}
                  className="space-y-3"
                >
                  <input
                    type="email"
                    required
                    placeholder="your@email.com"
                    value={requestEmail}
                    onChange={(e) => setRequestEmail(e.target.value)}
                    className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  {requestError && <p className="text-red-600 text-sm">{requestError}</p>}
                  <div className="flex gap-2">
                    <button
                      type="submit"
                      disabled={requestLoading || !requestEmail.trim()}
                      className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-bold py-3 rounded-xl text-sm transition-all"
                    >
                      {requestLoading ? "Submitting…" : "Notify Me →"}
                    </button>
                    <button
                      type="button"
                      onClick={() => setShowRequestModal(false)}
                      className="px-4 border border-slate-200 rounded-xl text-sm text-slate-500 hover:text-slate-700 transition-all"
                    >
                      Cancel
                    </button>
                  </div>
                </form>
              </>
            )}
          </div>
        </div>
      )}

      {/* Results */}
      {results && results.total_count > 0 && (
        <div className="grid lg:grid-cols-3 gap-8 items-start">
          {/* Left: results */}
          <div className="lg:col-span-2 space-y-5">
            {/* Duplicate purchase warning */}
            {duplicatePurchase && (
              <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-start gap-3 text-sm">
                <span className="text-amber-500 text-lg leading-none">⚠</span>
                <div>
                  <p className="font-semibold text-amber-800">You&apos;ve purchased this before</p>
                  <p className="text-amber-700 mt-0.5">
                    You bought{" "}
                    <strong>{duplicatePurchase.quantity.toLocaleString()} {duplicatePurchase.industry} leads</strong>
                    {duplicatePurchase.city ? ` in ${duplicatePurchase.city}, ` : " in "}
                    {duplicatePurchase.state} on{" "}
                    {new Date(duplicatePurchase.created_at).toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" })}.{" "}
                    <a
                      href={`/success?session_id=${duplicatePurchase.stripe_session_id}`}
                      className="underline font-semibold hover:text-amber-900"
                    >
                      Re-download that order
                    </a>{" "}
                    or continue to buy new leads added since then.
                  </p>
                </div>
              </div>
            )}
            {/* Result summary */}
            <div className="flex items-center justify-between flex-wrap gap-3">
              <div>
                <h2 className="text-2xl font-bold text-slate-900">
                  <span className="text-blue-600">{results.total_count.toLocaleString()}</span>{" "}
                  {results.query.industry} leads
                  {query?.zip_code && query.radius_miles
                    ? ` within ${query.radius_miles} mi of ${query.zip_code}`
                    : query?.state
                    ? ` in ${query.state}${query.city ? ` · ${query.city}` : ""}`
                    : ""}
                </h2>
                <div className="flex items-center gap-2 mt-1">
                  <p className="text-slate-500 text-sm">
                    Showing 10 sample leads · All fields included in download
                  </p>
                  {results.query.lead_type === "consumer" && (
                    <span className="inline-flex items-center gap-1 bg-teal-50 text-teal-700 text-xs font-semibold px-2 py-0.5 rounded-full">
                      Intent Leads
                    </span>
                  )}
                </div>
              </div>
              <div className="hidden sm:block text-right">
                <div className="text-sm text-slate-500">Avg. price</div>
                <div className="text-xl font-bold text-slate-900">
                  ${results.avg_lead_price.toFixed(3)}
                  <span className="text-sm font-normal text-slate-400">/lead</span>
                </div>
              </div>
            </div>

            {/* Free sample card */}
            {!sampleDone ? (
              <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-2xl p-5">
                <div className="flex items-start gap-4">
                  <div className="w-10 h-10 bg-blue-100 rounded-xl flex items-center justify-center shrink-0">
                    <svg className="w-5 h-5 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3M3 17V7a2 2 0 012-2h6l2 2h6a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
                    </svg>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-bold text-slate-800 mb-0.5">Try 5 real leads — free, no credit card</p>
                    <p className="text-xs text-slate-500 mb-3">Get a sample CSV instantly. See exactly what you're buying before you pay.</p>
                    <form onSubmit={handleGetSample} className="flex gap-2">
                      <input
                        type="email"
                        required
                        placeholder="your@email.com"
                        value={sampleEmail}
                        onChange={(e) => setSampleEmail(e.target.value)}
                        className="flex-1 border border-blue-200 bg-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                      />
                      <button
                        type="submit"
                        disabled={sampleLoading}
                        className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-semibold px-4 py-2 rounded-lg transition-colors whitespace-nowrap"
                      >
                        {sampleLoading ? "Preparing…" : "Get Free Sample"}
                      </button>
                    </form>
                    {sampleError && <p className="text-red-600 text-xs mt-2">{sampleError}</p>}
                  </div>
                </div>
              </div>
            ) : (
              <div className="bg-emerald-50 border border-emerald-200 rounded-2xl p-4 flex items-center gap-3">
                <svg className="w-5 h-5 text-emerald-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                </svg>
                <p className="text-sm text-emerald-700 font-medium">Sample downloaded! Ready to buy the full list?</p>
              </div>
            )}

            <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 text-xs text-slate-500 text-center">
              Phone, email, address, contact name, Yelp rating, years in business, and AI conversion score included in CSV.
              All leads are refreshed within the last 180 days and sold to at most 5 buyers.
            </div>
          </div>

          {/* Right: price calculator */}
          <div>
            <PriceCalculator
              totalCount={results.total_count}
              avgLeadPrice={results.avg_lead_price}
              industry={results.query.industry}
              state={results.query.state}
              city={results.query.city ?? undefined}
              leadType={results.query.lead_type ?? undefined}
              zipCode={results.query.zip_code ?? undefined}
              radiusMiles={results.query.radius_miles ?? undefined}
            />
          </div>
        </div>
      )}

      {/* Initial state — no search yet */}
      {!searched && !loading && (
        <div className="text-center py-16 text-slate-400">
          <div className="text-5xl mb-4">🔍</div>
          <p className="text-lg font-medium text-slate-500">Search for leads to get started</p>
          <p className="text-sm mt-2">Enter an industry and state above, or use ZIP + radius to search by proximity</p>
        </div>
      )}
    </div>
  );
}
