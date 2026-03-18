"use client";

import { submitServiceRequest } from "@/lib/api";
import type { PropertyType, ServiceRequestFormData, Timeline } from "@/types";
import { useState } from "react";

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

const SERVICES = [
  "Roofing",
  "Plumbing",
  "HVAC",
  "Solar",
  "Electrician",
  "Landscaping",
  "Pest Control",
  "Remodeling",
  "Flooring",
  "Painting",
  "Concrete",
  "Fencing",
  "Pool Service",
  "Tree Service",
  "Cleaning",
  "Handyman",
  "Foundation Repair",
  "Windows",
  "Gutters",
  "Insulation",
  "Waterproofing",
  "Garage Door",
  "Security",
  "Home Inspection",
  "Moving",
  "Siding",
  "Drywall",
  "Pressure Washing",
  "Appliance Repair",
  "Locksmith",
  "Auto Repair",
  "Dog Grooming",
  "Carpet Cleaning",
  "Mold Remediation",
  "Other",
];

const INITIAL: ServiceRequestFormData = {
  full_name: "",
  email: "",
  phone: "",
  zip_code: "",
  city: "",
  state: "",
  service_needed: "",
  project_description: "",
  timeline: "asap",
  property_type: "residential",
};

type SubmitState = "idle" | "submitting" | "success" | "error";

export default function ServiceRequestForm() {
  const [form, setForm] = useState<ServiceRequestFormData>(INITIAL);
  const [submitState, setSubmitState] = useState<SubmitState>("idle");
  const [errorMsg, setErrorMsg] = useState("");

  const set = (field: keyof ServiceRequestFormData, value: string) =>
    setForm((f) => ({ ...f, [field]: value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitState("submitting");
    setErrorMsg("");
    try {
      await submitServiceRequest(form);
      setSubmitState("success");
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Something went wrong. Please try again.");
      setSubmitState("error");
    }
  };

  if (submitState === "success") {
    return (
      <div className="bg-white rounded-3xl border border-emerald-200 shadow-sm p-10 text-center">
        <div className="w-16 h-16 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-6">
          <svg className="w-8 h-8 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <h2 className="text-2xl font-bold text-slate-900 mb-3">Request Submitted!</h2>
        <p className="text-slate-500 text-lg mb-6 max-w-sm mx-auto">
          Your service request is now in our database. Local contractors who specialize in{" "}
          <strong>{form.service_needed}</strong> in <strong>{form.city}, {form.state}</strong> will be
          reaching out to you soon.
        </p>
        <p className="text-sm text-slate-400">
          Make sure to check <strong>{form.email}</strong> and your phone for quotes.
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-3xl border border-slate-200 shadow-sm p-8 space-y-6">
      {/* Personal info */}
      <div>
        <h3 className="text-sm font-semibold text-slate-700 uppercase tracking-wide mb-4">Your Contact Info</h3>
        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Full Name *</label>
            <input
              type="text"
              required
              value={form.full_name}
              onChange={(e) => set("full_name", e.target.value)}
              placeholder="Jane Smith"
              className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Email *</label>
            <input
              type="email"
              required
              value={form.email}
              onChange={(e) => set("email", e.target.value)}
              placeholder="jane@example.com"
              className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Phone *</label>
            <input
              type="tel"
              required
              value={form.phone}
              onChange={(e) => set("phone", e.target.value)}
              placeholder="(555) 000-0000"
              className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">ZIP Code *</label>
            <input
              type="text"
              required
              maxLength={5}
              pattern="\d{5}"
              value={form.zip_code}
              onChange={(e) => set("zip_code", e.target.value)}
              placeholder="77001"
              className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">City *</label>
            <input
              type="text"
              required
              value={form.city}
              onChange={(e) => set("city", e.target.value)}
              placeholder="Houston"
              className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">State *</label>
            <select
              required
              value={form.state}
              onChange={(e) => set("state", e.target.value)}
              className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
            >
              <option value="">Select state…</option>
              {US_STATES.map(([code, name]) => (
                <option key={code} value={code}>{name}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Project info */}
      <div>
        <h3 className="text-sm font-semibold text-slate-700 uppercase tracking-wide mb-4">Project Details</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Service Needed *</label>
            <select
              required
              value={form.service_needed}
              onChange={(e) => set("service_needed", e.target.value)}
              className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
            >
              <option value="">Select a service…</option>
              {SERVICES.map((s) => (
                <option key={s} value={s.toLowerCase()}>{s}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Project Description</label>
            <textarea
              rows={3}
              value={form.project_description}
              onChange={(e) => set("project_description", e.target.value)}
              placeholder="Describe your project — size, current condition, specific needs, etc."
              className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500 resize-none"
            />
          </div>

          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Timeline *</label>
              <select
                required
                value={form.timeline}
                onChange={(e) => set("timeline", e.target.value as Timeline)}
                className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
              >
                <option value="asap">As soon as possible</option>
                <option value="1_3_months">Within 1–3 months</option>
                <option value="3_6_months">Within 3–6 months</option>
                <option value="planning">Just planning ahead</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Property Type *</label>
              <select
                required
                value={form.property_type}
                onChange={(e) => set("property_type", e.target.value as PropertyType)}
                className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
              >
                <option value="residential">Residential</option>
                <option value="commercial">Commercial</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      {submitState === "error" && (
        <div className="bg-red-50 text-red-700 text-sm p-4 rounded-xl">{errorMsg}</div>
      )}

      <button
        type="submit"
        disabled={submitState === "submitting"}
        className="w-full bg-teal-600 hover:bg-teal-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-bold py-4 rounded-xl text-lg transition-all hover:scale-[1.01] shadow-md shadow-teal-500/20"
      >
        {submitState === "submitting" ? "Submitting…" : "Submit Service Request — Free"}
      </button>

      <p className="text-xs text-slate-400 text-center">
        100% free. Your information is shared only with contractors relevant to your request.
        No spam, no marketing lists.
      </p>
    </form>
  );
}
