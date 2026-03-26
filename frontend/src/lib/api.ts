import type {
  AISearchResponse,
  CheckoutRequest,
  CheckoutResponse,
  LeadReportResponse,
  OrdersResponse,
  SampleRequestData,
  ServiceRequestFormData,
  ServiceRequestResponse,
  ShopResponse,
  StatsResponse,
  SubscriptionHistory,
  SubscriptionStatus,
} from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
// Server-side fetches use the internal Docker network URL to avoid round-tripping through the public internet
const SERVER_API_BASE = process.env.INTERNAL_API_URL ?? API_BASE;

export interface ShopFilters {
  hasYelp?: boolean;
  yelpMin?: number;
  yelpMax?: number;
  addedDays?: number;
  minQuality?: number;
  hasEmail?: boolean;
  hasContact?: boolean;
  hasAddress?: boolean;
  minConversion?: number;
}

export async function shopSearch(
  industry: string,
  state: string,
  city?: string,
  leadType?: string,
  zipCode?: string,
  radiusMiles?: number,
  filters?: ShopFilters,
): Promise<ShopResponse> {
  const params = new URLSearchParams({ industry });
  if (state) params.set("state", state);
  if (city) params.set("city", city);
  if (leadType && leadType !== "all") params.set("lead_type", leadType);
  if (zipCode) params.set("zip_code", zipCode);
  if (radiusMiles) params.set("radius_miles", String(radiusMiles));
  if (filters?.hasYelp) params.set("has_yelp", "true");
  if (filters?.yelpMin != null) params.set("yelp_min", String(filters.yelpMin));
  if (filters?.yelpMax != null) params.set("yelp_max", String(filters.yelpMax));
  if (filters?.addedDays != null) params.set("added_days", String(filters.addedDays));
  if (filters?.minQuality != null) params.set("min_quality", String(filters.minQuality));
  if (filters?.hasEmail) params.set("has_email", "true");
  if (filters?.hasContact) params.set("has_contact", "true");
  if (filters?.hasAddress) params.set("has_address", "true");
  if (filters?.minConversion != null) params.set("min_conversion", String(filters.minConversion));
  const res = await fetch(`${API_BASE}/api/shop?${params}`, { cache: "no-store" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? "Search failed");
  }
  return res.json();
}

export async function getStats(): Promise<StatsResponse> {
  try {
    const res = await fetch(`${SERVER_API_BASE}/api/shop/stats`, { next: { revalidate: 300 } });
    const fallback = { total_leads: 0, consumer_intent_count: 0, industries: [], pct_with_phone: 0, pct_with_email: 0, pct_with_contact: 0, pct_with_address: 0 };
    if (!res.ok) return fallback;
    return res.json();
  } catch {
    return { total_leads: 0, consumer_intent_count: 0, industries: [], pct_with_phone: 0, pct_with_email: 0, pct_with_contact: 0, pct_with_address: 0 };
  }
}

export async function createCheckout(body: CheckoutRequest): Promise<CheckoutResponse> {
  const res = await fetch(`${API_BASE}/api/checkout`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? "Checkout failed");
  }
  return res.json();
}

export function downloadUrl(sessionId: string): string {
  return `${API_BASE}/api/download?session_id=${encodeURIComponent(sessionId)}`;
}

export async function checkFulfilled(sessionId: string): Promise<boolean> {
  const res = await fetch(downloadUrl(sessionId), { method: "HEAD" }).catch(() => null);
  return res?.ok ?? false;
}

export async function reportLeads(
  sessionId: string,
  reason?: string,
): Promise<LeadReportResponse> {
  const res = await fetch(`${API_BASE}/api/leads/report`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, reason }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? "Report failed");
  }
  return res.json();
}

export async function requestFreeSample(data: SampleRequestData): Promise<Blob> {
  const res = await fetch(`${API_BASE}/api/leads/sample`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? "Sample request failed");
  }
  return res.blob();
}

export async function validatePromoCode(code: string): Promise<{ valid: boolean; discount_dollars: number }> {
  const res = await fetch(`${API_BASE}/api/credits/${encodeURIComponent(code.trim().toUpperCase())}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? "Invalid promo code");
  }
  return res.json();
}

export async function aiSearch(query: string, maxResults = 50): Promise<AISearchResponse> {
  const res = await fetch(`${API_BASE}/api/search/ai`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, max_results: maxResults }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? "AI search failed");
  }
  return res.json();
}

export async function getOrders(email: string): Promise<OrdersResponse> {
  const res = await fetch(
    `${API_BASE}/api/orders?email=${encodeURIComponent(email.trim().toLowerCase())}`,
    { cache: "no-store" },
  );
  if (!res.ok) return { purchases: [] };
  return res.json();
}

export async function createSubscriptionCheckout(email: string, referralCode?: string, plan?: string): Promise<{ checkout_url: string }> {
  const res = await fetch(`${API_BASE}/api/subscribe`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, plan: plan ?? "pro", referral_code: referralCode ?? null }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? "Subscription checkout failed");
  }
  return res.json();
}

export async function requestMagicLink(email: string): Promise<void> {
  await fetch(`${API_BASE}/api/subscription/auth/request`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
}

export async function submitServiceRequest(
  data: ServiceRequestFormData
): Promise<ServiceRequestResponse> {
  const res = await fetch(`${API_BASE}/api/leads/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? "Submission failed");
  }
  return res.json();
}
