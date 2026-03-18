import type {
  AISearchResponse,
  CheckoutRequest,
  CheckoutResponse,
  LeadReportResponse,
  SampleRequestData,
  ServiceRequestFormData,
  ServiceRequestResponse,
  ShopResponse,
  StatsResponse,
} from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function shopSearch(
  industry: string,
  state: string,
  city?: string,
  leadType?: string,
  zipCode?: string,
  radiusMiles?: number,
): Promise<ShopResponse> {
  const params = new URLSearchParams({ industry });
  if (state) params.set("state", state);
  if (city) params.set("city", city);
  if (leadType && leadType !== "all") params.set("lead_type", leadType);
  if (zipCode) params.set("zip_code", zipCode);
  if (radiusMiles) params.set("radius_miles", String(radiusMiles));
  const res = await fetch(`${API_BASE}/api/shop?${params}`, { cache: "no-store" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? "Search failed");
  }
  return res.json();
}

export async function getStats(): Promise<StatsResponse> {
  try {
    const res = await fetch(`${API_BASE}/api/shop/stats`, { next: { revalidate: 300 } });
    if (!res.ok) return { total_leads: 0, consumer_intent_count: 0, industries: [] };
    return res.json();
  } catch {
    return { total_leads: 0, consumer_intent_count: 0, industries: [] };
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
