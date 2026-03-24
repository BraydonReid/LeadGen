import type { Metadata } from "next";
import Link from "next/link";
import UTMCapture from "@/components/UTMCapture";
import "./globals.css";

export const metadata: Metadata = {
  title: "Take Your Lead Today — Contractor & Business Leads in Texas",
  description:
    "Buy verified Texas business leads by industry and city. Roofing, plumbing, HVAC, electrician, solar and more across Houston, Dallas, Austin, San Antonio. Starting at $0.10/lead. Instant CSV download.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-white text-slate-900 min-h-screen flex flex-col">
        <header className="bg-white border-b border-slate-100 sticky top-0 z-50 shadow-sm">
          <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
            <Link href="/" className="flex items-center gap-2">
              <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
                <svg className="w-5 h-5 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                </svg>
              </div>
              <span className="text-xl font-black text-slate-900 tracking-tight">Take Your Lead Today</span>
            </Link>

            <nav className="hidden md:flex items-center gap-7 text-sm font-medium text-slate-600">
              <Link href="/shop" className="hover:text-blue-600 transition-colors">Shop</Link>
              <Link href="/leads" className="hover:text-blue-600 transition-colors">Browse by Industry</Link>
              <Link href="/pricing" className="hover:text-blue-600 transition-colors">Pricing</Link>
              <Link href="/my-subscription" className="hover:text-blue-600 transition-colors">My Subscription</Link>
              <a href="/#how-it-works" className="hover:text-blue-600 transition-colors">How It Works</a>
              <Link href="/list-your-business" className="hover:text-blue-600 transition-colors">List Your Business</Link>
              <Link href="/request-service" className="hover:text-teal-600 transition-colors">Get Free Quotes</Link>
            </nav>

            <Link
              href="/shop"
              className="bg-blue-600 hover:bg-blue-700 text-white font-semibold px-5 py-2 rounded-lg text-sm transition-all"
            >
              Browse Leads →
            </Link>
          </div>
        </header>

        <UTMCapture />
        <main className="flex-1">{children}</main>

        <footer className="bg-slate-900 text-slate-400">
          <div className="max-w-6xl mx-auto px-6 py-12 grid sm:grid-cols-3 gap-10">
            <div>
              <div className="text-white font-black text-lg mb-3">Take Your Lead Today</div>
              <p className="text-sm leading-relaxed">
                Verified business leads for contractors and sales professionals across
                every city and industry. No contracts, no commitments.
              </p>
            </div>
            <div>
              <div className="text-white font-semibold text-sm mb-4">Product</div>
              <ul className="space-y-2 text-sm">
                <li><Link href="/shop" className="hover:text-white transition-colors">Browse Texas Leads</Link></li>
                <li><Link href="/pricing" className="hover:text-white transition-colors">Pricing</Link></li>
                <li><Link href="/subscribe" className="hover:text-white transition-colors">Subscribe — $99/month</Link></li>
                <li><Link href="/my-subscription" className="hover:text-white transition-colors">My Subscription</Link></li>
                <li><a href="/#how-it-works" className="hover:text-white transition-colors">How It Works</a></li>
                <li><Link href="/list-your-business" className="hover:text-white transition-colors">List Your Business</Link></li>
                <li><Link href="/request-service" className="hover:text-white transition-colors">Request a Service</Link></li>
              </ul>
            </div>
            <div>
              <div className="text-white font-semibold text-sm mb-4">Texas Cities</div>
              <ul className="space-y-2 text-sm">
                {[
                  ["Roofing leads — Houston", "/shop?industry=Roofing&state=TX&city=Houston"],
                  ["HVAC leads — Dallas", "/shop?industry=Hvac&state=TX&city=Dallas"],
                  ["Plumbing leads — Austin", "/shop?industry=Plumbing&state=TX&city=Austin"],
                  ["Electrician leads — San Antonio", "/shop?industry=Electrician&state=TX&city=San+Antonio"],
                  ["Solar leads — Texas", "/shop?industry=Solar&state=TX"],
                  ["Contractor leads — Fort Worth", "/shop?industry=Remodeling&state=TX&city=Fort+Worth"],
                ].map(([label, href]) => (
                  <li key={href}>
                    <Link href={href} className="hover:text-white transition-colors">{label}</Link>
                  </li>
                ))}
              </ul>
            </div>
          </div>
          <div className="border-t border-slate-800 px-6 py-4 text-center text-xs text-slate-600">
            &copy; {new Date().getFullYear()} LeadGen. All rights reserved.
          </div>
        </footer>
      </body>
    </html>
  );
}
