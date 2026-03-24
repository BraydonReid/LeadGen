import type { MetadataRoute } from "next";

const BASE_URL = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";

interface PageSummary {
  slug_industry: string;
  slug_city: string;
  industry: string;
  city: string;
}

async function getSeoPages(): Promise<PageSummary[]> {
  try {
    const res = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL}/api/seo/pages?min_count=10`,
      { cache: "no-store" }
    );
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const pages = await getSeoPages();

  // Static routes
  const static_routes: MetadataRoute.Sitemap = [
    { url: BASE_URL, priority: 1.0, changeFrequency: "daily" },
    { url: `${BASE_URL}/shop`, priority: 0.9, changeFrequency: "hourly" },
    { url: `${BASE_URL}/leads`, priority: 0.8, changeFrequency: "daily" },
    { url: `${BASE_URL}/request-service`, priority: 0.5, changeFrequency: "monthly" },
  ];

  // One entry per unique industry (e.g. /leads/roofing)
  const industrySet = new Set<string>();
  const industry_routes: MetadataRoute.Sitemap = [];
  for (const p of pages) {
    if (!industrySet.has(p.slug_industry)) {
      industrySet.add(p.slug_industry);
      industry_routes.push({
        url: `${BASE_URL}/leads/${p.slug_industry}`,
        priority: 0.75,
        changeFrequency: "weekly",
      });
    }
  }

  // One entry per city×industry page (e.g. /leads/roofing/dallas-tx)
  const city_routes: MetadataRoute.Sitemap = pages.map((p) => ({
    url: `${BASE_URL}/leads/${p.slug_industry}/${p.slug_city}`,
    priority: 0.7,
    changeFrequency: "weekly" as const,
  }));

  return [...static_routes, ...industry_routes, ...city_routes];
}
