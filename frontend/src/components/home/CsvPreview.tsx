export default function CsvPreview() {
  const columns = [
    { header: "business_name", value: "Smith's HVAC Services", note: "" },
    { header: "contact_name", value: "John Smith", note: "Decision-maker" },
    { header: "contact_title", value: "Owner", note: "" },
    { header: "phone", value: "(512) 555-0182", note: "Verified" },
    { header: "email", value: "john@smithshvac.com", note: "Verified" },
    { header: "full_address", value: "1204 Oak Hill Dr, Austin, TX 78735", note: "" },
    { header: "website", value: "smithshvac.com", note: "" },
    { header: "linkedin_url", value: "linkedin.com/in/johnsmith-hvac", note: "" },
    { header: "yelp_rating", value: "4.7", note: "★ Reputation" },
    { header: "review_count", value: "143", note: "Active business" },
    { header: "years_in_business", value: "12", note: "Established" },
    { header: "ai_conversion_score", value: "87", note: "AI-ranked" },
    { header: "date_added", value: "2025-11-14", note: "Fresh" },
  ];

  return (
    <section className="py-20 bg-white">
      <div className="max-w-6xl mx-auto px-6">
        <div className="text-center mb-10">
          <span className="inline-block bg-blue-100 text-blue-700 text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wider mb-4">
            What you get
          </span>
          <h2 className="text-3xl lg:text-4xl font-bold text-slate-900 mb-4">
            Every lead includes 18 data points
          </h2>
          <p className="text-slate-500 text-lg max-w-2xl mx-auto">
            No other Texas lead provider includes AI quality scores, Yelp reputation, or years in business.
            These fields let your sales team prioritize calls — before picking up the phone.
          </p>
        </div>

        {/* Sample CSV table */}
        <div className="bg-slate-50 rounded-2xl border border-slate-200 overflow-hidden shadow-sm">
          <div className="flex items-center gap-1.5 px-4 py-3 bg-slate-100 border-b border-slate-200">
            <div className="w-3 h-3 rounded-full bg-red-400" />
            <div className="w-3 h-3 rounded-full bg-yellow-400" />
            <div className="w-3 h-3 rounded-full bg-emerald-400" />
            <span className="ml-2 text-xs text-slate-400 font-mono">leads_hvac_TX.csv</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs font-mono">
              <thead>
                <tr className="bg-slate-800 text-left">
                  {columns.map((col) => (
                    <th key={col.header} className="px-3 py-2 text-slate-300 font-semibold whitespace-nowrap">
                      {col.header}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-slate-200">
                  {columns.map((col) => (
                    <td key={col.header} className="px-3 py-2.5 text-slate-700 whitespace-nowrap">
                      {col.value}
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        {/* Callouts */}
        <div className="grid sm:grid-cols-3 gap-4 mt-8">
          {[
            {
              icon: "🤖",
              title: "AI Conversion Score",
              desc: "Each lead is scored 0–100 by AI for conversion likelihood. Sort your CRM by score to call your best prospects first.",
              highlight: true,
            },
            {
              icon: "⭐",
              title: "Yelp Rating + Reviews",
              desc: "Know if you're calling a 4.7★ business with 143 reviews or a struggling 2.1★ — tailor your pitch accordingly.",
              highlight: false,
            },
            {
              icon: "🕐",
              title: "Years in Business",
              desc: "A 12-year-old HVAC company is a very different conversation from a startup. We surface this automatically.",
              highlight: false,
            },
          ].map(({ icon, title, desc, highlight }) => (
            <div
              key={title}
              className={`rounded-xl p-5 border ${
                highlight
                  ? "bg-blue-50 border-blue-200"
                  : "bg-slate-50 border-slate-200"
              }`}
            >
              <div className="text-2xl mb-2">{icon}</div>
              <div className={`font-bold text-sm mb-1 ${highlight ? "text-blue-800" : "text-slate-800"}`}>
                {title}
              </div>
              <div className="text-slate-500 text-xs leading-relaxed">{desc}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
