"use client";

import { useState, useEffect, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const INDUSTRIES = [
  "Roofing","HVAC","Plumbing","Electrical","Landscaping","Concrete",
  "Flooring","Painting","Windows","Gutters","Tree Service","Pest Control",
  "Cleaning Services","Remodeling","Solar","Security Systems","Attorney",
  "Dentist","Accountant","Auto Repair","Photography","Real Estate",
];
const STATES = [
  "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA",
  "KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
  "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT",
  "VA","WA","WV","WI","WY",
];

function fmt(iso: string) {
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}
function fmtDate(dt: string | undefined) {
  if (!dt) return "your next billing date";
  return new Date(dt).toLocaleDateString("en-US", { month: "long", day: "numeric" });
}

function authHeaders(session: string) {
  return { "Content-Type": "application/json", "x-sub-session": session };
}

// ── Magic link request screen ──────────────────────────────────────────────

function MagicLinkGate({ onSession }: { onSession: (s: string, e: string) => void }) {
  const [email, setEmail] = useState(() => {
    if (typeof window !== "undefined") return localStorage.getItem("leadgen_buyer_email") ?? "";
    return "";
  });
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Check for existing valid session on mount
  useEffect(() => {
    const session = localStorage.getItem("leadgen_sub_session");
    const savedEmail = localStorage.getItem("leadgen_buyer_email");
    if (session && savedEmail) {
      onSession(session, savedEmail);
    }
  }, [onSession]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/subscription/auth/request`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim().toLowerCase() }),
      });
      if (!res.ok) throw new Error("Request failed");
      localStorage.setItem("leadgen_buyer_email", email.trim().toLowerCase());
      setSent(true);
    } catch {
      setError("Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  if (sent) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center px-4">
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-8 w-full max-w-sm text-center">
          <div className="text-4xl mb-4">📬</div>
          <h2 className="text-xl font-black text-slate-900 mb-2">Check your inbox</h2>
          <p className="text-slate-500 text-sm mb-2">
            We sent a sign-in link to <span className="font-semibold text-slate-700">{email}</span>.
          </p>
          <p className="text-slate-400 text-xs">Link expires in 20 minutes.</p>
          <button
            onClick={() => setSent(false)}
            className="mt-6 text-blue-600 hover:underline text-sm"
          >
            Use a different email
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center px-4">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-8 w-full max-w-sm">
        <h1 className="text-2xl font-black text-slate-900 mb-1">My Subscription</h1>
        <p className="text-slate-500 text-sm mb-6">
          Enter your email and we&apos;ll send you a secure sign-in link.
        </p>
        <form onSubmit={handleSubmit} className="space-y-3">
          <input
            type="email"
            required
            placeholder="your@email.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          {error && <p className="text-red-600 text-sm">{error}</p>}
          <button
            type="submit"
            disabled={loading || !email.trim()}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-bold py-3 rounded-xl text-sm transition-all"
          >
            {loading ? "Sending…" : "Send Sign-In Link →"}
          </button>
        </form>
        <div className="mt-6 pt-4 border-t border-slate-100">
          <p className="text-center text-xs text-slate-500 font-semibold mb-3">Not subscribed? Choose a plan:</p>
          <div className="grid grid-cols-2 gap-3">
            <a href="/subscribe?plan=starter"
              className="block text-center border border-slate-200 rounded-xl px-4 py-3 hover:border-blue-300 hover:bg-blue-50 transition-all">
              <div className="font-bold text-slate-800 text-sm">Starter</div>
              <div className="text-blue-600 font-black text-lg">$29.99<span className="text-slate-400 text-xs font-normal">/mo</span></div>
              <div className="text-slate-400 text-xs">50 leads/month</div>
            </a>
            <a href="/subscribe?plan=pro"
              className="block text-center border-2 border-blue-500 rounded-xl px-4 py-3 bg-blue-50 hover:bg-blue-100 transition-all">
              <div className="font-bold text-slate-800 text-sm">Pro</div>
              <div className="text-blue-600 font-black text-lg">$99.99<span className="text-slate-400 text-xs font-normal">/mo</span></div>
              <div className="text-slate-400 text-xs">300 leads/month</div>
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Main dashboard ──────────────────────────────────────────────────────────

function Dashboard({ session, email, onSignOut }: { session: string; email: string; onSignOut: () => void }) {
  const [sub, setSub] = useState<Record<string, unknown> | null>(null);
  const [downloads, setDownloads] = useState<Record<string, unknown>[]>([]);
  const [referral, setReferral] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Download form
  const [industry, setIndustry] = useState("Roofing");
  const [state, setState] = useState("TX");
  const [city, setCity] = useState("");
  const [quantity, setQuantity] = useState(50);
  const [downloading, setDownloading] = useState(false);
  const [dlError, setDlError] = useState<string | null>(null);

  // Referral UI
  const [copied, setCopied] = useState(false);
  const [refInput, setRefInput] = useState("");
  const [applyingRef, setApplyingRef] = useState(false);
  const [refMsg, setRefMsg] = useState<string | null>(null);

  // Developer API
  const [apiKeyCopied, setApiKeyCopied] = useState(false);
  const [generatingKey, setGeneratingKey] = useState(false);
  const [webhookInput, setWebhookInput] = useState("");
  const [savingWebhook, setSavingWebhook] = useState(false);
  const [webhookMsg, setWebhookMsg] = useState<string | null>(null);

  // Cancel
  const [canceling, setCanceling] = useState(false);
  const [cancelMsg, setCancelMsg] = useState<string | null>(null);
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const headers = authHeaders(session);
      const [statusRes, historyRes, referralRes] = await Promise.all([
        fetch(`${API_BASE}/api/subscription/status`, { headers, cache: "no-store" }),
        fetch(`${API_BASE}/api/subscription/history`, { headers, cache: "no-store" }),
        fetch(`${API_BASE}/api/subscription/referral`, { headers, cache: "no-store" }),
      ]);

      if (statusRes.status === 401) { onSignOut(); return; }

      const statusData = await statusRes.json();
      setSub(statusData);
      if (historyRes.ok) {
        const h = await historyRes.json();
        setDownloads((h.downloads ?? []) as Record<string, unknown>[]);
      }
      if (referralRes.ok) {
        setReferral(await referralRes.json());
      }
    } catch {
      setError("Failed to load subscription data.");
    } finally {
      setLoading(false);
    }
  }, [session, onSignOut]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (sub?.webhook_url) setWebhookInput((sub.webhook_url as string) ?? "");
  }, [sub]);

  async function handleDownload(e: React.FormEvent) {
    e.preventDefault();
    setDlError(null);
    setDownloading(true);
    try {
      const res = await fetch(`${API_BASE}/api/subscription/download`, {
        method: "POST",
        headers: authHeaders(session),
        body: JSON.stringify({ industry, state, city: city.trim() || null, quantity }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error((data as { detail?: string }).detail ?? "Download failed.");
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `leads_${industry.toLowerCase().replace(/ /g, "_")}_${state}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      await load();
    } catch (err) {
      setDlError(err instanceof Error ? err.message : "Download failed.");
    } finally {
      setDownloading(false);
    }
  }

  async function handleApplyReferral(e: React.FormEvent) {
    e.preventDefault();
    setApplyingRef(true);
    setRefMsg(null);
    try {
      const res = await fetch(`${API_BASE}/api/subscription/referral/apply`, {
        method: "POST",
        headers: authHeaders(session),
        body: JSON.stringify({ referral_code: refInput.trim().toUpperCase() }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error((data as { detail?: string }).detail ?? "Invalid code.");
      setRefMsg(`✓ Applied! You earned ${(data as { bonus_credits?: number }).bonus_credits} bonus credits.`);
      setRefInput("");
      await load();
    } catch (err) {
      setRefMsg(err instanceof Error ? err.message : "Failed.");
    } finally {
      setApplyingRef(false);
    }
  }

  async function handleCancel() {
    setCanceling(true);
    setCancelMsg(null);
    try {
      const res = await fetch(`${API_BASE}/api/subscription/cancel`, {
        method: "POST",
        headers: authHeaders(session),
      });
      const data = await res.json();
      if (!res.ok) throw new Error((data as { detail?: string }).detail ?? "Cancellation failed.");
      const until = (data as { access_until?: string }).access_until;
      setCancelMsg(`Subscription canceled. You have access until ${until ? fmtDate(until) : "your next billing date"}.`);
      setShowCancelConfirm(false);
      await load();
    } catch (err) {
      setCancelMsg(err instanceof Error ? err.message : "Failed to cancel.");
    } finally {
      setCanceling(false);
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <p className="text-slate-400 animate-pulse">Loading your subscription…</p>
      </div>
    );
  }

  if (error || !sub?.subscribed) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center px-4">
        <div className="text-center">
          <p className="text-red-600 mb-3">{error ?? "No active subscription found."}</p>
          <button onClick={onSignOut} className="text-blue-600 hover:underline text-sm">
            Sign in with a different email
          </button>
        </div>
      </div>
    );
  }

  const creditsRemaining = (sub.credits_remaining as number) ?? 0;
  const rolloverCredits = (sub.rollover_credits as number) ?? 0;
  const totalCredits = creditsRemaining + rolloverCredits;
  const leadsPerMonth = (sub.leads_per_month as number) ?? 300;
  const usedPct = Math.min(100, Math.round(((leadsPerMonth - creditsRemaining) / leadsPerMonth) * 100));

  return (
    <div className="bg-slate-50 min-h-screen">
      <div className="max-w-4xl mx-auto px-6 py-12 space-y-8">

        {/* Header */}
        <div className="flex items-start justify-between flex-wrap gap-4">
          <div>
            <h1 className="text-3xl font-black text-slate-900">My Subscription</h1>
            <p className="text-slate-500 text-sm mt-1">{email}</p>
          </div>
          <span className="inline-flex items-center gap-1.5 bg-emerald-100 text-emerald-700 text-sm font-bold px-3 py-1.5 rounded-full">
            <span className="w-2 h-2 bg-emerald-500 rounded-full" />
            Active — {(sub.plan as string) === "starter" ? "Starter" : (sub.plan as string) === "agency" ? "Agency" : "Pro"} Plan
          </span>
        </div>

        {/* Credits card */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
          <div className="flex items-start justify-between flex-wrap gap-4 mb-4">
            <div>
              <div className="text-slate-500 text-sm mb-1">Credits this month</div>
              <div className="text-4xl font-black text-slate-900">
                {creditsRemaining}
                <span className="text-xl text-slate-400 font-normal"> / {leadsPerMonth}</span>
              </div>
              {rolloverCredits > 0 && (
                <div className="text-emerald-600 text-sm font-semibold mt-1">
                  +{rolloverCredits} rolled over from last month
                </div>
              )}
            </div>
            {(sub.current_period_end as string | null) && (
              <div className="text-right">
                <div className="text-slate-400 text-xs">Resets on</div>
                <div className="text-slate-700 font-semibold text-sm">{fmtDate(sub.current_period_end as string)}</div>
              </div>
            )}
          </div>
          <div className="h-2.5 bg-slate-100 rounded-full overflow-hidden">
            <div className="h-full bg-blue-500 rounded-full transition-all" style={{ width: `${usedPct}%` }} />
          </div>
          <div className="text-xs text-slate-400 mt-1.5">{leadsPerMonth - creditsRemaining} leads downloaded this month</div>
        </div>

        {/* Download form */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
          <h2 className="text-lg font-black text-slate-900 mb-1">Download Leads</h2>
          <p className="text-slate-500 text-sm mb-5">
            Freshest matching leads — sorted by AI conversion score.
          </p>
          <form onSubmit={handleDownload} className="space-y-4">
            <div className="grid sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1.5">Industry</label>
                <select value={industry} onChange={(e) => setIndustry(e.target.value)}
                  className="w-full border border-slate-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                  {INDUSTRIES.map((i) => <option key={i}>{i}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1.5">State</label>
                <select value={state} onChange={(e) => setState(e.target.value)}
                  className="w-full border border-slate-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                  {STATES.map((s) => <option key={s}>{s}</option>)}
                </select>
              </div>
            </div>
            <div className="grid sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1.5">City <span className="text-slate-400 font-normal">(optional)</span></label>
                <input type="text" placeholder="e.g. Houston" value={city} onChange={(e) => setCity(e.target.value)}
                  className="w-full border border-slate-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1.5">
                  Quantity <span className="text-slate-400 font-normal">(max {totalCredits})</span>
                </label>
                <input type="number" min={1} max={totalCredits}
                  value={quantity} onChange={(e) => setQuantity(Math.min(Number(e.target.value), totalCredits))}
                  className="w-full border border-slate-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
            </div>
            {dlError && <p className="text-red-600 text-sm bg-red-50 rounded-xl px-4 py-2">{dlError}</p>}
            <button type="submit" disabled={downloading || totalCredits <= 0}
              className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-bold px-8 py-3 rounded-xl text-sm transition-all">
              {downloading ? "Preparing CSV…" : `Download ${quantity} Leads →`}
            </button>
            {totalCredits <= 0 && (
              <p className="text-amber-600 text-sm">No credits remaining. Resets on {fmtDate(sub.current_period_end as string)}.</p>
            )}
          </form>
        </div>

        {/* Developer Access — Pro/Agency only */}
        {(sub.plan === "pro" || sub.plan === "agency") && (
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
            <h2 className="text-lg font-black text-slate-900 mb-1">Developer Access</h2>
            <p className="text-slate-500 text-sm mb-4">
              Use your API key to fetch leads as JSON from any app or script. Pro/Agency only.
            </p>

            {/* API Key */}
            <div className="mb-5">
              <label className="block text-xs font-semibold text-slate-600 mb-1.5">API Key</label>
              {sub.api_key ? (
                <div className="flex gap-2">
                  <input
                    readOnly
                    value={sub.api_key as string}
                    className="flex-1 font-mono text-xs border border-slate-200 rounded-xl px-3 py-2.5 bg-slate-50 text-slate-700 focus:outline-none"
                  />
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(sub.api_key as string);
                      setApiKeyCopied(true);
                      setTimeout(() => setApiKeyCopied(false), 2000);
                    }}
                    className="bg-slate-700 hover:bg-slate-800 text-white text-xs font-bold px-3 py-2.5 rounded-xl transition-all whitespace-nowrap"
                  >
                    {apiKeyCopied ? "Copied!" : "Copy"}
                  </button>
                  <button
                    onClick={async () => {
                      setGeneratingKey(true);
                      try {
                        const res = await fetch(`${API_BASE}/api/subscription/api-key`, {
                          method: "POST", headers: authHeaders(session),
                        });
                        if (res.ok) { const d = await res.json(); setSub(s => ({ ...s!, api_key: d.api_key })); }
                      } finally { setGeneratingKey(false); }
                    }}
                    disabled={generatingKey}
                    className="border border-slate-200 hover:border-slate-300 text-slate-500 hover:text-slate-700 text-xs font-semibold px-3 py-2.5 rounded-xl transition-all disabled:opacity-50 whitespace-nowrap"
                  >
                    {generatingKey ? "…" : "Regenerate"}
                  </button>
                </div>
              ) : (
                <button
                  onClick={async () => {
                    setGeneratingKey(true);
                    try {
                      const res = await fetch(`${API_BASE}/api/subscription/api-key`, {
                        method: "POST", headers: authHeaders(session),
                      });
                      if (res.ok) { const d = await res.json(); setSub(s => ({ ...s!, api_key: d.api_key })); }
                    } finally { setGeneratingKey(false); }
                  }}
                  disabled={generatingKey}
                  className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-bold px-5 py-2.5 rounded-xl transition-all"
                >
                  {generatingKey ? "Generating…" : "Generate API Key"}
                </button>
              )}
              <p className="text-xs text-slate-400 mt-2">
                <code className="bg-slate-100 px-1.5 py-0.5 rounded text-xs">GET /api/leads?industry=hvac&state=TX&limit=50</code>
                {" "}with <code className="bg-slate-100 px-1.5 py-0.5 rounded text-xs">Authorization: Bearer {"{"}{"}"}api_key{"}"}</code>
              </p>
            </div>

            {/* Webhook URL */}
            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1.5">Webhook URL <span className="text-slate-400 font-normal">(optional)</span></label>
              <div className="flex gap-2">
                <input
                  type="url"
                  placeholder="https://your-app.com/webhook/leads"
                  value={webhookInput}
                  onChange={(e) => setWebhookInput(e.target.value)}
                  className="flex-1 border border-slate-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <button
                  onClick={async () => {
                    setSavingWebhook(true);
                    setWebhookMsg(null);
                    try {
                      const res = await fetch(`${API_BASE}/api/subscription/webhook`, {
                        method: "PATCH",
                        headers: authHeaders(session),
                        body: JSON.stringify({ webhook_url: webhookInput.trim() || null }),
                      });
                      setWebhookMsg(res.ok ? "Saved!" : "Failed to save.");
                    } finally { setSavingWebhook(false); }
                  }}
                  disabled={savingWebhook}
                  className="bg-slate-700 hover:bg-slate-800 disabled:opacity-50 text-white text-xs font-bold px-4 py-2.5 rounded-xl transition-all whitespace-nowrap"
                >
                  {savingWebhook ? "Saving…" : "Save"}
                </button>
              </div>
              {webhookMsg && (
                <p className={`text-xs mt-1 ${webhookMsg === "Saved!" ? "text-emerald-600" : "text-red-600"}`}>{webhookMsg}</p>
              )}
              <p className="text-xs text-slate-400 mt-1">We&apos;ll POST the JSON lead payload here after each API download.</p>
            </div>
          </div>
        )}

        {/* Referral program */}
        {referral && (
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
            <h2 className="text-lg font-black text-slate-900 mb-1">Referral Program</h2>
            <p className="text-slate-500 text-sm mb-4">
              Share your link. When someone subscribes with it, you both get{" "}
              <span className="font-semibold text-blue-600">50 free credits</span>.
            </p>
            <div className="flex gap-2 mb-3">
              <input
                readOnly
                value={(referral.referral_url as string) ?? ""}
                className="flex-1 border border-slate-200 rounded-xl px-3 py-2.5 text-sm bg-slate-50 text-slate-600 focus:outline-none"
              />
              <button
                onClick={() => {
                  navigator.clipboard.writeText((referral.referral_url as string) ?? "");
                  setCopied(true);
                  setTimeout(() => setCopied(false), 2000);
                }}
                className="bg-blue-600 hover:bg-blue-700 text-white font-bold px-4 py-2.5 rounded-xl text-sm transition-all whitespace-nowrap"
              >
                {copied ? "Copied!" : "Copy Link"}
              </button>
            </div>
            {((referral.referrals_count as number) ?? 0) > 0 && (
              <p className="text-emerald-600 text-sm font-semibold">
                {referral.referrals_count as number} subscriber{(referral.referrals_count as number) !== 1 ? "s" : ""} referred
                · {referral.bonus_credits_earned as number} bonus credits earned
              </p>
            )}

            {/* Apply someone else's code */}
            {!(sub.referred_by_code as string) && (
              <form onSubmit={handleApplyReferral} className="mt-4 pt-4 border-t border-slate-100 flex gap-2">
                <input
                  type="text"
                  placeholder="Enter a referral code"
                  value={refInput}
                  onChange={(e) => setRefInput(e.target.value)}
                  className="flex-1 border border-slate-200 rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <button type="submit" disabled={applyingRef || !refInput.trim()}
                  className="bg-slate-700 hover:bg-slate-800 disabled:opacity-50 text-white font-bold px-4 py-2.5 rounded-xl text-sm transition-all whitespace-nowrap">
                  {applyingRef ? "Applying…" : "Apply Code"}
                </button>
              </form>
            )}
            {refMsg && (
              <p className={`text-sm mt-2 ${refMsg.startsWith("✓") ? "text-emerald-600" : "text-red-600"}`}>{refMsg}</p>
            )}
          </div>
        )}

        {/* Download history */}
        {downloads.length > 0 && (
          <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
            <h2 className="text-lg font-black text-slate-900 mb-4">Download History</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-slate-400 uppercase tracking-wide border-b border-slate-100">
                    <th className="pb-2 font-semibold">Industry</th>
                    <th className="pb-2 font-semibold">Location</th>
                    <th className="pb-2 font-semibold text-right">Leads</th>
                    <th className="pb-2 font-semibold text-right">Date</th>
                  </tr>
                </thead>
                <tbody>
                  {downloads.map((d, i) => (
                    <tr key={i} className="border-b border-slate-50 last:border-0">
                      <td className="py-2.5 font-medium text-slate-800">{d.industry as string}</td>
                      <td className="py-2.5 text-slate-500">
                        {d.city ? `${d.city as string}, ${d.state as string}` : d.state as string}
                      </td>
                      <td className="py-2.5 text-right text-blue-600 font-semibold">{d.quantity as number}</td>
                      <td className="py-2.5 text-right text-slate-400">{fmt(d.downloaded_at as string)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Upgrade prompt for Starter → Pro */}
        {(sub.plan as string) === "starter" && (
          <div className="bg-blue-50 border border-blue-200 rounded-2xl p-5 flex items-center justify-between gap-4 flex-wrap">
            <div>
              <div className="font-bold text-slate-900 text-sm">Upgrade to Pro</div>
              <div className="text-slate-500 text-xs mt-0.5">Get 300 leads/month instead of 50 — $99.99/mo</div>
            </div>
            <a href="/subscribe?plan=pro"
              className="bg-blue-600 hover:bg-blue-700 text-white font-bold px-5 py-2.5 rounded-xl text-sm transition-all whitespace-nowrap">
              Upgrade →
            </a>
          </div>
        )}

        {/* Upgrade prompt for Pro → Agency */}
        {(sub.plan as string) === "pro" && (
          <div className="bg-violet-50 border border-violet-200 rounded-2xl p-5 flex items-center justify-between gap-4 flex-wrap">
            <div>
              <div className="font-bold text-slate-900 text-sm">Upgrade to Agency</div>
              <div className="text-slate-500 text-xs mt-0.5">Get 1,000 leads/month instead of 300 — $299/mo (~$0.30/lead)</div>
            </div>
            <a href="/subscribe?plan=agency"
              className="bg-violet-600 hover:bg-violet-700 text-white font-bold px-5 py-2.5 rounded-xl text-sm transition-all whitespace-nowrap">
              Upgrade →
            </a>
          </div>
        )}

        {/* Cancel / sign out */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <button onClick={onSignOut} className="text-slate-500 hover:text-slate-700 text-sm underline">
              Sign out
            </button>
            {sub.status !== "canceled" && sub.status !== "canceling" && (
              <div>
                {!showCancelConfirm ? (
                  <button
                    onClick={() => setShowCancelConfirm(true)}
                    className="text-red-500 hover:text-red-700 text-sm underline"
                  >
                    Cancel subscription
                  </button>
                ) : (
                  <div className="flex items-center gap-3">
                    <span className="text-sm text-slate-600">Cancel at end of billing period?</span>
                    <button
                      onClick={handleCancel}
                      disabled={canceling}
                      className="bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white text-xs font-bold px-4 py-2 rounded-lg transition-all"
                    >
                      {canceling ? "Canceling…" : "Yes, Cancel"}
                    </button>
                    <button
                      onClick={() => setShowCancelConfirm(false)}
                      className="text-slate-500 hover:text-slate-700 text-xs underline"
                    >
                      Keep subscription
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
          {cancelMsg && (
            <p className={`text-sm mt-3 ${cancelMsg.includes("canceled") ? "text-amber-600" : "text-red-600"}`}>
              {cancelMsg}
            </p>
          )}
          {sub.status === "canceling" && (
            <p className="text-amber-600 text-sm mt-3">
              Your subscription is set to cancel on {fmtDate(sub.current_period_end as string)}. You retain full access until then.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Page shell ──────────────────────────────────────────────────────────────

function MySubscriptionInner() {
  const searchParams = useSearchParams();
  const [session, setSession] = useState<string | null>(null);
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    // On return from magic link verify, session is already in localStorage
    const s = localStorage.getItem("leadgen_sub_session");
    const e = localStorage.getItem("leadgen_buyer_email");
    if (s && e) { setSession(s); setEmail(e); }

    // Fresh subscription redirect
    if (searchParams.get("subscribed") === "1") {
      // Clear subscribed param cleanly
      window.history.replaceState({}, "", "/my-subscription");
    }
  }, [searchParams]);

  function handleSession(s: string, e: string) {
    localStorage.setItem("leadgen_sub_session", s);
    localStorage.setItem("leadgen_buyer_email", e);
    setSession(s);
    setEmail(e);
  }

  function handleSignOut() {
    localStorage.removeItem("leadgen_sub_session");
    setSession(null);
    setEmail(null);
  }

  if (!session || !email) {
    return <MagicLinkGate onSession={handleSession} />;
  }

  return <Dashboard session={session} email={email} onSignOut={handleSignOut} />;
}

export default function MySubscriptionPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
      </div>
    }>
      <MySubscriptionInner />
    </Suspense>
  );
}
