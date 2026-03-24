"use client";

import { useState } from "react";
import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const INDUSTRIES = [
  "Roofing","HVAC","Plumbing","Electrical","Landscaping","Concrete",
  "Flooring","Painting","Windows","Gutters","Tree Service","Pest Control",
  "Cleaning Services","Remodeling","Solar","Security Systems","Attorney",
  "Dentist","Accountant","Auto Repair","Photography","Real Estate",
  "Pest Control","Fencing","Insulation","Pool Service","Handyman",
  "Moving Services","Appliance Repair","Garage Door","Other",
];

const STATES = [
  "TX","AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL",
  "IN","IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE",
  "NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD",
  "TN","UT","VT","VA","WA","WV","WI","WY",
];

export default function ListYourBusinessPage() {
  const [form, setForm] = useState({
    business_name: "",
    industry: "Roofing",
    city: "",
    state: "TX",
    phone: "",
    email: "",
    website: "",
    contact_name: "",
    full_address: "",
  });
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<"success" | "duplicate" | "error" | null>(null);
  const [error, setError] = useState<string | null>(null);

  function update(field: string, value: string) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/list-business`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (!res.ok) throw new Error((data as { detail?: string }).detail ?? "Submission failed.");
      setResult((data as { already_listed?: boolean }).already_listed ? "duplicate" : "success");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submission failed.");
    } finally {
      setLoading(false);
    }
  }

  if (result === "success") {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center px-4">
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-10 w-full max-w-md text-center">
          <div className="w-16 h-16 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h2 className="text-2xl font-black text-slate-900 mb-2">You&apos;re Listed!</h2>
          <p className="text-slate-500 text-sm mb-6">
            <strong>{form.business_name}</strong> has been added to our lead database.
            Contractors searching for {form.industry.toLowerCase()} businesses in {form.city}, {form.state}{" "}
            can now find and contact you.
          </p>
          <div className="space-y-3">
            <Link
              href="/shop"
              className="block w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 rounded-xl text-sm transition-all text-center"
            >
              Browse Other Leads →
            </Link>
            <button
              onClick={() => { setResult(null); setForm({ business_name: "", industry: "Roofing", city: "", state: "TX", phone: "", email: "", website: "", contact_name: "", full_address: "" }); }}
              className="block w-full text-slate-500 hover:text-slate-700 text-sm underline"
            >
              Submit another business
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (result === "duplicate") {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center px-4">
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-10 w-full max-w-md text-center">
          <div className="text-4xl mb-4">📋</div>
          <h2 className="text-2xl font-black text-slate-900 mb-2">Already Listed</h2>
          <p className="text-slate-500 text-sm mb-6">
            <strong>{form.business_name}</strong> in {form.city}, {form.state} is already in our database.
          </p>
          <Link href="/shop" className="block w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 rounded-xl text-sm transition-all text-center">
            Browse Leads →
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-slate-50 min-h-screen py-16 px-4">
      <div className="max-w-xl mx-auto">

        {/* Hero */}
        <div className="text-center mb-10">
          <h1 className="text-4xl font-black text-slate-900 mb-3">List Your Business</h1>
          <p className="text-slate-500 text-base">
            Get your business in front of contractors, buyers, and service providers
            actively searching your area. It&apos;s free and takes 60 seconds.
          </p>
        </div>

        {/* Benefits */}
        <div className="grid grid-cols-3 gap-4 mb-8">
          {[
            ["Free", "No cost to list your business"],
            ["Instant", "Live in the database immediately"],
            ["Targeted", "Matched to buyers in your industry"],
          ].map(([title, desc]) => (
            <div key={title} className="bg-white rounded-xl border border-slate-200 p-4 text-center">
              <div className="text-slate-900 font-black text-sm mb-1">{title}</div>
              <div className="text-slate-500 text-xs">{desc}</div>
            </div>
          ))}
        </div>

        {/* Form */}
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-8">
          <form onSubmit={handleSubmit} className="space-y-5">

            {/* Required */}
            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1.5">
                Business Name <span className="text-red-500">*</span>
              </label>
              <input
                type="text" required
                placeholder="e.g. Smith Roofing LLC"
                value={form.business_name}
                onChange={(e) => update("business_name", e.target.value)}
                className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1.5">
                  Industry <span className="text-red-500">*</span>
                </label>
                <select
                  required value={form.industry}
                  onChange={(e) => update("industry", e.target.value)}
                  className="w-full border border-slate-200 rounded-xl px-3 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {INDUSTRIES.map((i) => <option key={i}>{i}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-600 mb-1.5">
                  State <span className="text-red-500">*</span>
                </label>
                <select
                  required value={form.state}
                  onChange={(e) => update("state", e.target.value)}
                  className="w-full border border-slate-200 rounded-xl px-3 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {STATES.map((s) => <option key={s}>{s}</option>)}
                </select>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-600 mb-1.5">
                City <span className="text-red-500">*</span>
              </label>
              <input
                type="text" required
                placeholder="e.g. Houston"
                value={form.city}
                onChange={(e) => update("city", e.target.value)}
                className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            {/* Optional */}
            <div className="border-t border-slate-100 pt-5">
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-4">
                Contact Details (optional — improves visibility)
              </p>
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-600 mb-1.5">Phone</label>
                    <input
                      type="tel"
                      placeholder="(555) 555-5555"
                      value={form.phone}
                      onChange={(e) => update("phone", e.target.value)}
                      className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-600 mb-1.5">Email</label>
                    <input
                      type="email"
                      placeholder="you@business.com"
                      value={form.email}
                      onChange={(e) => update("email", e.target.value)}
                      className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-600 mb-1.5">Website</label>
                  <input
                    type="url"
                    placeholder="https://yourbusiness.com"
                    value={form.website}
                    onChange={(e) => update("website", e.target.value)}
                    className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-600 mb-1.5">Contact Name</label>
                    <input
                      type="text"
                      placeholder="John Smith"
                      value={form.contact_name}
                      onChange={(e) => update("contact_name", e.target.value)}
                      className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-600 mb-1.5">Address</label>
                    <input
                      type="text"
                      placeholder="123 Main St"
                      value={form.full_address}
                      onChange={(e) => update("full_address", e.target.value)}
                      className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                </div>
              </div>
            </div>

            {error && (
              <p className="text-red-600 text-sm bg-red-50 rounded-xl px-4 py-3">{error}</p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-black py-4 rounded-xl text-base transition-all"
            >
              {loading ? "Submitting…" : "List My Business — Free →"}
            </button>

            <p className="text-center text-xs text-slate-400">
              Your info may be purchased by contractors or sales professionals.{" "}
              <a href="mailto:support@takeyourleadtoday.com" className="text-blue-600 hover:underline">
                Contact us
              </a>{" "}
              to remove your listing.
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}
