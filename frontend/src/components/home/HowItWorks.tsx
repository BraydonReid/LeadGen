const steps = [
  {
    number: "01",
    title: "Search Your Industry",
    description:
      "Enter your target industry and location. Our database covers roofing, plumbing, HVAC, solar, electricians, landscaping, and dozens more.",
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>
    ),
  },
  {
    number: "02",
    title: "Pick Your Quantity",
    description:
      "Use our price calculator to choose exactly how many leads you need. Bulk discounts kick in automatically — up to 45% off for large orders.",
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
      </svg>
    ),
  },
  {
    number: "03",
    title: "Pay & Download",
    description:
      "Secure checkout with Stripe. The moment your payment is confirmed, download your CSV file with business name, phone, website, and more.",
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
      </svg>
    ),
  },
];

export default function HowItWorks() {
  return (
    <section id="how-it-works" className="bg-slate-50 py-20">
      <div className="max-w-6xl mx-auto px-6">
        <div className="text-center mb-14">
          <h2 className="text-3xl lg:text-4xl font-bold text-slate-900 mb-4">How It Works</h2>
          <p className="text-slate-500 text-lg max-w-xl mx-auto">
            From search to download in under 3 minutes. No phone calls, no commitments.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-8">
          {steps.map((step, i) => (
            <div key={step.number} className="relative">
              {i < steps.length - 1 && (
                <div className="hidden md:block absolute top-8 left-full w-full h-0.5 bg-blue-100 -translate-x-4 z-0" />
              )}
              <div className="bg-white rounded-2xl p-8 shadow-sm border border-slate-100 relative z-10 h-full">
                <div className="flex items-center gap-4 mb-5">
                  <div className="w-12 h-12 bg-blue-600 rounded-xl flex items-center justify-center text-white flex-shrink-0">
                    {step.icon}
                  </div>
                  <span className="text-4xl font-black text-slate-300">{step.number}</span>
                </div>
                <h3 className="text-xl font-bold text-slate-900 mb-3">{step.title}</h3>
                <p className="text-slate-500 leading-relaxed">{step.description}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
