import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "LeadGen — Business Leads Marketplace",
  description:
    "Buy verified business leads by industry and location. Roofing, plumbing, HVAC, solar and more. Starting at $0.10/lead. Instant CSV download.",
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
              <span className="text-xl font-black text-slate-900 tracking-tight">LeadGen</span>
            </Link>

            <nav className="hidden md:flex items-center gap-7 text-sm font-medium text-slate-600">
              <Link href="/shop" className="hover:text-blue-600 transition-colors">Shop</Link>
              <a href="/#how-it-works" className="hover:text-blue-600 transition-colors">How It Works</a>
              <a href="/#industries" className="hover:text-blue-600 transition-colors">Industries</a>
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

        <main className="flex-1">{children}</main>

        <footer className="bg-slate-900 text-slate-400">
          <div className="max-w-6xl mx-auto px-6 py-12 grid sm:grid-cols-3 gap-10">
            <div>
              <div className="text-white font-black text-lg mb-3">LeadGen</div>
              <p className="text-sm leading-relaxed">
                Affordable business leads for small businesses and independent sales professionals.
                No contracts, no commitments.
              </p>
            </div>
            <div>
              <div className="text-white font-semibold text-sm mb-4">Product</div>
              <ul className="space-y-2 text-sm">
                <li><Link href="/shop" className="hover:text-white transition-colors">Browse Leads</Link></li>
                <li><a href="/#how-it-works" className="hover:text-white transition-colors">How It Works</a></li>
                <li><a href="/#industries" className="hover:text-white transition-colors">Industries</a></li>
                <li><Link href="/request-service" className="hover:text-white transition-colors">Request a Service</Link></li>
              </ul>
            </div>
            <div>
              <div className="text-white font-semibold text-sm mb-4">Popular Searches</div>
              <ul className="space-y-2 text-sm">
                {[
                  ["Roofing leads — Texas", "/shop?industry=Roofing&state=TX"],
                  ["Plumbing leads — California", "/shop?industry=Plumbing&state=CA"],
                  ["HVAC leads — Florida", "/shop?industry=Hvac&state=FL"],
                  ["Solar leads — California", "/shop?industry=Solar&state=CA"],
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
