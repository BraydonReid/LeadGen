import type { PricedLead } from "@/types";

function QualityBadge({ score }: { score: number | null }) {
  if (score === null || score === undefined) return <span className="text-slate-300 text-xs">—</span>;
  const color =
    score >= 80
      ? "bg-emerald-100 text-emerald-700"
      : score >= 50
      ? "bg-yellow-100 text-yellow-700"
      : "bg-red-100 text-red-700";
  return (
    <span className={`inline-block text-xs font-semibold px-2 py-0.5 rounded-full ${color}`}>
      {score}
    </span>
  );
}

function ConversionBadge({ score }: { score: number | null | undefined }) {
  if (score === null || score === undefined) return null;
  const color =
    score >= 75
      ? "bg-violet-100 text-violet-700"
      : score >= 50
      ? "bg-indigo-100 text-indigo-700"
      : "bg-slate-100 text-slate-500";
  return (
    <span className={`inline-block text-xs font-semibold px-2 py-0.5 rounded-full ${color}`} title="AI Conversion Score">
      ✦ {score}
    </span>
  );
}

function ReviewBadge({ rating, count }: { rating?: number | null; count?: number | null }) {
  if (!rating && !count) return <span className="text-slate-300 text-xs">—</span>;
  return (
    <span className="inline-flex items-center gap-1" title={`${count ?? "?"} reviews`}>
      {rating != null && (
        <span className="inline-flex items-center gap-0.5 bg-amber-50 text-amber-600 text-xs font-semibold px-1.5 py-0.5 rounded-full border border-amber-200">
          ★ {rating.toFixed(1)}
        </span>
      )}
      {count != null && (
        <span className="text-xs text-slate-400">({count})</span>
      )}
    </span>
  );
}

function LeadTypeBadge({ type }: { type: string }) {
  if (type === "consumer") {
    return (
      <span className="inline-block bg-teal-100 text-teal-700 text-xs font-semibold px-2 py-0.5 rounded-full whitespace-nowrap">
        Intent Lead
      </span>
    );
  }
  return (
    <span className="inline-block bg-blue-100 text-blue-700 text-xs font-semibold px-2 py-0.5 rounded-full">
      Business
    </span>
  );
}

export default function LeadPreviewTable({ leads }: { leads: PricedLead[] }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="bg-slate-50 border-b border-slate-200">
            <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Business</th>
            <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">City</th>
            <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Phone</th>
            <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Website</th>
            <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Type</th>
            <th className="px-4 py-3 text-left text-xs font-semibold text-amber-500 uppercase tracking-wide">Reviews</th>
            <th className="px-4 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide">Quality</th>
            <th className="px-4 py-3 text-left text-xs font-semibold text-violet-400 uppercase tracking-wide">AI Score</th>
            <th className="px-4 py-3 text-right text-xs font-semibold text-slate-500 uppercase tracking-wide">Value</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {leads.map((lead) => (
            <tr key={lead.id} className="hover:bg-slate-50 transition-colors">
              <td className="px-4 py-3 max-w-[160px]">
                <div className="font-medium text-slate-900 truncate">{lead.business_name}</div>
                {lead.years_in_business != null && lead.years_in_business > 0 && (
                  <div className="text-xs text-slate-400 mt-0.5">{lead.years_in_business}yr in business</div>
                )}
              </td>
              <td className="px-4 py-3 text-slate-600">
                <div>{lead.city}</div>
                {lead.full_address && (
                  <div className="text-xs text-slate-400 truncate max-w-[130px]">{lead.full_address}</div>
                )}
              </td>
              <td className="px-4 py-3 text-slate-600 font-mono text-xs whitespace-nowrap">
                {lead.phone ?? "—"}
              </td>
              <td className="px-4 py-3 text-slate-500 text-xs max-w-[110px] truncate">
                {lead.website ? lead.website.replace(/^https?:\/\//, "") : "—"}
              </td>
              <td className="px-4 py-3">
                <LeadTypeBadge type={lead.lead_type ?? "business"} />
              </td>
              <td className="px-4 py-3">
                <ReviewBadge rating={lead.yelp_rating} count={lead.review_count} />
              </td>
              <td className="px-4 py-3">
                <QualityBadge score={lead.quality_score} />
              </td>
              <td className="px-4 py-3">
                <ConversionBadge score={lead.conversion_score} />
              </td>
              <td className="px-4 py-3 text-right text-emerald-600 font-semibold text-xs">
                ${lead.unit_price.toFixed(2)}
              </td>
            </tr>
          ))}
          {/* Blurred ghost rows */}
          {Array.from({ length: 5 }).map((_, i) => (
            <tr key={`ghost-${i}`} className="select-none pointer-events-none">
              {[160, 80, 90, 110, 70, 70, 40, 40, 40].map((w, j) => (
                <td key={j} className="px-4 py-3">
                  <span
                    className="block bg-slate-200 rounded animate-pulse"
                    style={{ height: 12, width: w, opacity: 0.4 - i * 0.07 }}
                  />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
