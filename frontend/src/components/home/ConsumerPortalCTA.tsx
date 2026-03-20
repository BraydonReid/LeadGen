import Link from "next/link";

export default function ConsumerPortalCTA({ intentLeadCount }: { intentLeadCount: number }) {
  const formatted = intentLeadCount > 0 ? intentLeadCount.toLocaleString() : null;

  return (
    <section className="py-20 bg-gradient-to-br from-teal-50 to-slate-50">
      <div className="max-w-6xl mx-auto px-6">
        <div className="grid lg:grid-cols-2 gap-12 items-center">
          {/* Left: for businesses buying leads */}
          <div>
            <div className="inline-flex items-center gap-2 bg-teal-100 text-teal-700 rounded-full px-4 py-1.5 text-sm font-semibold mb-6">
              <span className="w-2 h-2 bg-teal-500 rounded-full animate-pulse" />
              Consumer Intent Leads
            </div>
            <h2 className="text-3xl lg:text-4xl font-bold text-slate-900 mb-4 leading-tight">
              Texas Homeowners Actively
              <br />
              <span className="text-teal-600">Seeking Your Services</span>
            </h2>
            <p className="text-slate-600 text-lg mb-6 leading-relaxed">
              Beyond business directories, we offer{" "}
              <strong className="text-slate-900">
                {formatted ? `${formatted} consumer intent leads` : "consumer intent leads"}
              </strong>{" "}
              — real Texas homeowners who pulled building permits and are actively hiring contractors
              right now. These leads convert at dramatically higher rates.
            </p>
            <ul className="space-y-3 text-slate-600 mb-8">
              {[
                "Texas homeowners actively hiring contractors",
                "From real building permit records — verified intent",
                "Houston, Dallas, Austin, San Antonio and more",
                "Filter by 'Intent Leads' in the shop",
              ].map((item) => (
                <li key={item} className="flex items-center gap-3">
                  <span className="w-5 h-5 bg-teal-500 rounded-full flex items-center justify-center flex-shrink-0">
                    <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                    </svg>
                  </span>
                  {item}
                </li>
              ))}
            </ul>
            <Link
              href="/shop?lead_type=consumer"
              className="inline-flex items-center gap-2 bg-teal-600 hover:bg-teal-700 text-white font-bold px-8 py-4 rounded-xl text-lg transition-all hover:scale-105 shadow-lg shadow-teal-500/20"
            >
              Browse Intent Leads →
            </Link>
          </div>

          {/* Right: for homeowners submitting */}
          <div className="bg-white rounded-3xl border border-teal-200 shadow-lg p-8">
            <div className="flex items-center gap-3 mb-5">
              <div className="w-10 h-10 bg-teal-100 rounded-xl flex items-center justify-center">
                <svg className="w-5 h-5 text-teal-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
                </svg>
              </div>
              <div className="text-sm font-semibold text-teal-700 bg-teal-50 px-3 py-1 rounded-full">
                For Homeowners
              </div>
            </div>
            <h3 className="text-2xl font-bold text-slate-900 mb-3">
              Need a Texas contractor?
            </h3>
            <p className="text-slate-500 mb-6 leading-relaxed">
              Submit a free service request and get connected with Texas professionals
              who specialize in exactly what you need — no fees, no spam.
            </p>
            <ul className="space-y-2 text-sm text-slate-600 mb-8">
              {[
                "Completely free — no fees ever",
                "Get multiple competing quotes",
                "Residential & commercial projects",
                "All Texas cities covered",
              ].map((item) => (
                <li key={item} className="flex items-center gap-2">
                  <span className="text-teal-500 font-bold">✓</span>
                  {item}
                </li>
              ))}
            </ul>
            <Link
              href="/request-service"
              className="block text-center bg-slate-900 hover:bg-slate-800 text-white font-bold px-8 py-4 rounded-xl text-lg transition-all"
            >
              Submit a Service Request →
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
