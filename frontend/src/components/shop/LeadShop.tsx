"use client";

import { aiSearch, requestFreeSample, shopSearch } from "@/lib/api";
import type { AISearchIntent, ShopResponse } from "@/types";
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

  // AI search mode
  const [searchMode, setSearchMode] = useState<"standard" | "ai">("standard");
  const [aiIntent, setAiIntent] = useState<AISearchIntent | null>(null);

  // Free sample state
  const [sampleEmail, setSampleEmail] = useState("");
  const [sampleLoading, setSampleLoading] = useState(false);
  const [sampleDone, setSampleDone] = useState(false);
  const [sampleError, setSampleError] = useState<string | null>(null);

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
          <p className="text-yellow-700 text-sm">
            Try a different industry, expand your radius, or broaden your location. Our database grows daily.
          </p>
        </div>
      )}

      {/* Results */}
      {results && results.total_count > 0 && (
        <div className="grid lg:grid-cols-3 gap-8 items-start">
          {/* Left: results */}
          <div className="lg:col-span-2 space-y-5">
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
              Phone, email, and full address are included in the downloaded CSV.
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
