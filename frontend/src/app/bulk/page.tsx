"use client";

import { useState } from "react";
import Link from "next/link";

const US_STATES = [
  "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA",
  "KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
  "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT",
  "VA","WA","WV","WI","WY",
];

const INDUSTRIES = [
  "Roofing","HVAC","Plumbing","Electrician","Solar","Remodeling","Landscaping",
  "Tree Service","Painting","Flooring","Concrete","Fencing","Windows & Doors",
  "Siding","Gutters","Waterproofing","Foundation Repair","Pool Service",
  "Pest Control","Cleaning","Law Firm","Insurance","Real Estate","Dentist",
  "Chiropractor","Auto Repair","General Contractor","Other",
];

export default function BulkQuotePage() {
  const [form, setForm] = useState({
    name: "",
    email: "",
    company: "",
    industry: "",
    state: "TX",
    quantity: 5000,
    notes: "",
  });
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: name === "quantity" ? parseInt(value) || 0 : value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatus("loading");
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/bulk-quote`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      if (!res.ok) throw new Error("Request failed");
      setStatus("success");
    } catch {
      setStatus("error");
    }
  };

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <section className="bg-slate-900 text-white py-16">
        <div className="max-w-3xl mx-auto px-6 text-center">
          <span className="inline-block bg-blue-500/20 border border-blue-400/30 rounded-full px-4 py-1.5 text-sm text-blue-300 mb-6">
            5,000+ leads
          </span>
          <h1 className="text-4xl lg:text-5xl font-extrabold mb-4">Get a Custom Bulk Quote</h1>
          <p className="text-slate-300 text-lg max-w-xl mx-auto">
            Need thousands of leads? Tell us what you need and we&apos;ll send a custom
            quote within 24 hours — usually much faster.
          </p>
        </div>
      </section>

      <div className="max-w-5xl mx-auto px-6 py-16 grid lg:grid-cols-3 gap-12">
        {/* Form */}
        <div className="lg:col-span-2">
          {status === "success" ? (
            <div className="bg-white rounded-2xl border border-emerald-200 p-10 text-center">
              <div className="w-16 h-16 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg className="w-8 h-8 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h2 className="text-2xl font-bold text-slate-900 mb-2">Request received!</h2>
              <p className="text-slate-600 mb-6">
                We&apos;ll send your custom quote to <strong>{form.email}</strong> within 24 hours.
              </p>
              <Link href="/shop" className="text-blue-600 hover:underline font-medium">
                Browse leads now while you wait →
              </Link>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="bg-white rounded-2xl border border-slate-200 p-8 space-y-5">
              <div className="grid sm:grid-cols-2 gap-5">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1.5">Your name *</label>
                  <input
                    name="name"
                    required
                    value={form.name}
                    onChange={handleChange}
                    className="w-full border border-slate-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Jane Smith"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1.5">Email address *</label>
                  <input
                    name="email"
                    type="email"
                    required
                    value={form.email}
                    onChange={handleChange}
                    className="w-full border border-slate-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="jane@yourcompany.com"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">Company (optional)</label>
                <input
                  name="company"
                  value={form.company}
                  onChange={handleChange}
                  className="w-full border border-slate-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Acme Solar LLC"
                />
              </div>

              <div className="grid sm:grid-cols-2 gap-5">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1.5">Industry *</label>
                  <select
                    name="industry"
                    required
                    value={form.industry}
                    onChange={handleChange}
                    className="w-full border border-slate-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                  >
                    <option value="">Select an industry…</option>
                    {INDUSTRIES.map((ind) => (
                      <option key={ind} value={ind}>{ind}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1.5">State *</label>
                  <select
                    name="state"
                    required
                    value={form.state}
                    onChange={handleChange}
                    className="w-full border border-slate-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                  >
                    {US_STATES.map((s) => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">
                  How many leads do you need? *
                </label>
                <input
                  name="quantity"
                  type="number"
                  required
                  min={1000}
                  step={500}
                  value={form.quantity}
                  onChange={handleChange}
                  className="w-full border border-slate-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <p className="text-xs text-slate-400 mt-1">Minimum 1,000 leads for bulk pricing</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">
                  Additional notes (optional)
                </label>
                <textarea
                  name="notes"
                  rows={3}
                  value={form.notes}
                  onChange={handleChange}
                  className="w-full border border-slate-200 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                  placeholder="e.g. Need leads only with email, or only cities with 100k+ population, or prefer consumer intent leads…"
                />
              </div>

              {status === "error" && (
                <p className="text-red-600 text-sm">Something went wrong. Please email us directly.</p>
              )}

              <button
                type="submit"
                disabled={status === "loading"}
                className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white font-bold py-3.5 rounded-xl text-base transition-all"
              >
                {status === "loading" ? "Sending…" : "Request Custom Quote →"}
              </button>
              <p className="text-center text-xs text-slate-400">
                We respond within 24 hours · No obligation · Free to ask
              </p>
            </form>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          <div className="bg-white rounded-2xl border border-slate-200 p-6">
            <div className="text-sm font-semibold text-slate-900 mb-4">Bulk pricing tiers</div>
            <div className="space-y-3">
              {[
                { qty: "1,000", price: "$0.54/lead", discount: "25% off" },
                { qty: "5,000", price: "$0.46/lead", discount: "35% off" },
                { qty: "10,000+", price: "$0.39/lead", discount: "45% off" },
              ].map(({ qty, price, discount }) => (
                <div key={qty} className="flex items-center justify-between text-sm">
                  <span className="text-slate-600">{qty} leads</span>
                  <div className="text-right">
                    <span className="font-bold text-slate-900">{price}</span>
                    <span className="ml-2 text-xs text-emerald-600 font-semibold">{discount}</span>
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-4 pt-4 border-t border-slate-100 text-xs text-slate-400">
              Prices shown for standard leads. Consumer intent leads are 1.5× listed price.
              Final quote depends on industry, state, and data requirements.
            </div>
          </div>

          <div className="bg-blue-50 rounded-2xl border border-blue-100 p-6">
            <div className="text-sm font-semibold text-slate-900 mb-3">What&apos;s included</div>
            <ul className="space-y-2 text-sm text-slate-600">
              {[
                "Business name, phone, email, address",
                "AI conversion score (0–100)",
                "Yelp rating + review count",
                "Facebook & Instagram links",
                "Contact name where available",
                "Instant CSV download",
                "Max 5 resales — enforced",
              ].map((item) => (
                <li key={item} className="flex items-center gap-2">
                  <svg className="w-4 h-4 text-blue-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                  </svg>
                  {item}
                </li>
              ))}
            </ul>
          </div>

          <div className="text-center text-sm text-slate-500">
            Rather browse yourself?{" "}
            <Link href="/shop" className="text-blue-600 hover:underline font-medium">
              Shop leads →
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
