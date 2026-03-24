import LeadShop from "@/components/shop/LeadShop";
import { Suspense } from "react";

export const metadata = {
  title: "Shop Business Leads — Take Your Lead Today",
  description: "Search and buy verified Texas contractor and business leads by industry and city. Houston, Dallas, Austin, San Antonio and all Texas cities. Instant CSV download.",
};

export default function ShopPage() {
  return (
    <div className="bg-slate-50 min-h-screen">
      {/* Page header */}
      <div className="bg-white border-b border-slate-100">
        <div className="max-w-6xl mx-auto px-6 py-8">
          <h1 className="text-3xl font-bold text-slate-900 mb-2">Texas Lead Marketplace</h1>
          <p className="text-slate-500">
            Search Texas contractor and business leads by industry and city. Preview leads,
            select your quantity, and download your CSV instantly after checkout.
          </p>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-6 py-8">
        <Suspense fallback={<div className="text-slate-400 py-20 text-center">Loading…</div>}>
          <LeadShop />
        </Suspense>
      </div>
    </div>
  );
}
