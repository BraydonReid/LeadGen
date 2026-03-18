import type { Lead } from "@/types";

export default function LeadTable({ leads }: { leads: Lead[] }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-gray-200">
      <table className="min-w-full text-sm">
        <thead className="bg-gray-50 text-gray-500 uppercase text-xs">
          <tr>
            <th className="px-4 py-3 text-left">Business</th>
            <th className="px-4 py-3 text-left">City</th>
            <th className="px-4 py-3 text-left">State</th>
            <th className="px-4 py-3 text-left">Phone</th>
            <th className="px-4 py-3 text-left">Website</th>
            <th className="px-4 py-3 text-left">Email</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 bg-white">
          {leads.map((lead) => (
            <tr key={lead.id} className="hover:bg-gray-50">
              <td className="px-4 py-3 font-medium text-gray-900">{lead.business_name}</td>
              <td className="px-4 py-3 text-gray-600">{lead.city}</td>
              <td className="px-4 py-3 text-gray-600">{lead.state}</td>
              <td className="px-4 py-3 text-gray-600">{lead.phone || "—"}</td>
              <td className="px-4 py-3 text-blue-600 truncate max-w-[150px]">
                {lead.website ? (
                  <span className="truncate">{lead.website.replace(/^https?:\/\//, "")}</span>
                ) : (
                  "—"
                )}
              </td>
              <td className="px-4 py-3">
                <span className="bg-gray-100 text-gray-400 text-xs px-2 py-1 rounded">
                  Unlocked on purchase
                </span>
              </td>
            </tr>
          ))}
          {/* Blurred ghost rows to hint at more data */}
          {[...Array(5)].map((_, i) => (
            <tr key={`blur-${i}`} className="opacity-40 select-none pointer-events-none">
              <td className="px-4 py-3">
                <span className="bg-gray-200 rounded h-4 w-32 block" />
              </td>
              <td className="px-4 py-3">
                <span className="bg-gray-200 rounded h-4 w-20 block" />
              </td>
              <td className="px-4 py-3">
                <span className="bg-gray-200 rounded h-4 w-8 block" />
              </td>
              <td className="px-4 py-3">
                <span className="bg-gray-200 rounded h-4 w-24 block" />
              </td>
              <td className="px-4 py-3">
                <span className="bg-gray-200 rounded h-4 w-28 block" />
              </td>
              <td className="px-4 py-3">
                <span className="bg-gray-200 rounded h-4 w-28 block" />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
