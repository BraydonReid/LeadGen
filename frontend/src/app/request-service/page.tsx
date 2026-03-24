import ServiceRequestForm from "@/components/request-service/ServiceRequestForm";
import { Suspense } from "react";

export const metadata = {
  title: "Get Free Quotes From Contractors — Take Your Lead Today",
  description:
    "Tell us what you need and get matched with local Texas contractors. Houston, Dallas, Austin, San Antonio and all Texas cities. 100% free, no obligation.",
};

export default function RequestServicePage() {
  return (
    <div className="bg-slate-50 min-h-screen">
      {/* Hero header */}
      <div className="bg-gradient-to-br from-slate-900 via-teal-900 to-slate-900 text-white">
        <div className="max-w-3xl mx-auto px-6 py-16 text-center">
          <div className="inline-flex items-center gap-2 bg-teal-500/20 border border-teal-400/30 rounded-full px-4 py-1.5 text-sm text-teal-300 mb-6">
            <span className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
            Free Service — No Obligation
          </div>
          <h1 className="text-4xl lg:text-5xl font-extrabold mb-5 leading-tight">
            Get Free Quotes from
            <br />
            <span className="text-teal-400">Texas Contractors</span>
          </h1>
          <p className="text-lg text-slate-300 max-w-xl mx-auto leading-relaxed">
            Tell us what you need. We match your request with verified Texas service professionals
            who will reach out with competitive quotes — completely free to you.
          </p>

          <div className="flex flex-wrap justify-center gap-6 mt-8 text-sm text-slate-400">
            {["No cost to you ever", "Multiple quotes to compare", "Residential & commercial", "All Texas cities"].map((item) => (
              <span key={item} className="flex items-center gap-2">
                <svg className="w-4 h-4 text-teal-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                </svg>
                {item}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Form */}
      <div className="max-w-2xl mx-auto px-6 py-10 -mt-4">
        <Suspense fallback={<div className="text-slate-400 text-center py-10">Loading…</div>}>
          <ServiceRequestForm />
        </Suspense>
      </div>

      {/* How it works */}
      <div className="max-w-3xl mx-auto px-6 pb-16">
        <h2 className="text-xl font-bold text-slate-700 text-center mb-8">How It Works</h2>
        <div className="grid sm:grid-cols-3 gap-6">
          {[
            { step: "1", title: "Submit Your Request", desc: "Fill out the form with your project details and contact info. Takes under 2 minutes." },
            { step: "2", title: "Contractors Are Notified", desc: "Local professionals who match your service and location are alerted to your request." },
            { step: "3", title: "Get Quotes & Compare", desc: "Contractors reach out directly with quotes. You choose who to hire — zero pressure." },
          ].map(({ step, title, desc }) => (
            <div key={step} className="bg-white rounded-2xl border border-slate-200 p-6 text-center">
              <div className="w-10 h-10 bg-teal-600 text-white rounded-full flex items-center justify-center font-black text-lg mx-auto mb-4">{step}</div>
              <h3 className="font-bold text-slate-900 mb-2">{title}</h3>
              <p className="text-slate-500 text-sm leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
