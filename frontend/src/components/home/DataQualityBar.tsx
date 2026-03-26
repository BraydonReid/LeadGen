interface Props {
  pctPhone: number;
  pctEmail: number;
  pctContact: number;
  pctAddress: number;
}

export default function DataQualityBar({ pctPhone, pctEmail, pctContact, pctAddress }: Props) {
  const stats = [
    { label: "Phone Number", value: pctPhone, color: "bg-blue-500" },
    { label: "Email Address", value: pctEmail, color: "bg-emerald-500" },
    { label: "Contact Name", value: pctContact, color: "bg-violet-500" },
    { label: "Street Address", value: pctAddress, color: "bg-amber-500" },
  ];

  return (
    <section className="py-10 bg-slate-900">
      <div className="max-w-6xl mx-auto px-6">
        <p className="text-center text-slate-400 text-xs font-semibold uppercase tracking-widest mb-6">
          Live data quality — Texas business leads
        </p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          {stats.map(({ label, value, color }) => (
            <div key={label} className="text-center">
              <div className="text-3xl font-black text-white mb-1">
                {value > 0 ? `${value.toFixed(0)}%` : "—"}
              </div>
              <div className="text-slate-400 text-xs mb-2">{label}</div>
              <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
                <div
                  className={`h-full ${color} rounded-full transition-all`}
                  style={{ width: `${Math.min(value, 100)}%` }}
                />
              </div>
            </div>
          ))}
        </div>
        <p className="text-center text-slate-500 text-xs mt-6">
          AI conversion scores included on every lead. No other Texas lead provider includes this.
        </p>
      </div>
    </section>
  );
}
