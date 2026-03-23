export interface Lead {
  id: number;
  business_name: string;
  industry: string;
  city: string;
  state: string;
  website: string | null;
  phone: string | null;
  quality_score: number | null;
  conversion_score?: number | null;
  lead_type: "business" | "consumer";
  full_address: string | null;
  yelp_rating?: number | null;
  review_count?: number | null;
  years_in_business?: number | null;
}

export interface PricedLead extends Lead {
  unit_price: number;
}

export interface SearchQuery {
  industry: string;
  state: string;
  city: string | null;
  lead_type: string | null;
  zip_code: string | null;
  radius_miles: number | null;
  has_yelp?: boolean | null;
  yelp_min?: number | null;
  yelp_max?: number | null;
  added_days?: number | null;
  min_quality?: number | null;
}

export interface ShopResponse {
  total_count: number;
  avg_lead_price: number;
  preview: PricedLead[];
  query: SearchQuery;
}

export interface IndustryStat {
  industry: string;
  count: number;
}

export interface StatsResponse {
  total_leads: number;
  consumer_intent_count: number;
  industries: IndustryStat[];
}

export interface CheckoutRequest {
  industry: string;
  state: string;
  city?: string;
  quantity: number;
  lead_type?: string;
  zip_code?: string;
  radius_miles?: number;
  promo_code?: string;
  utm_source?: string;
  utm_medium?: string;
  utm_campaign?: string;
  referrer?: string;
}

export interface LeadReportResponse {
  credit_code: string;
  discount_amount_dollars: number;
}

export interface SampleRequestData {
  email: string;
  industry: string;
  state: string;
  city?: string;
  lead_type?: string;
  zip_code?: string;
  radius_miles?: number;
}

export interface CheckoutResponse {
  checkout_url: string;
  total: number;
  discount_pct: number;
  avg_lead_price: number;
}

export type Timeline = "asap" | "1_3_months" | "3_6_months" | "planning";
export type PropertyType = "residential" | "commercial";

export interface ServiceRequestFormData {
  full_name: string;
  email: string;
  phone: string;
  zip_code: string;
  city: string;
  state: string;
  service_needed: string;
  project_description: string;
  timeline: Timeline;
  property_type: PropertyType;
}

export interface ServiceRequestResponse {
  success: boolean;
  message: string;
}

export interface AISearchIntent {
  industry: string | null;
  state: string | null;
  city: string | null;
  lead_type: string | null;
  has_website: boolean | null;
  has_email: boolean | null;
  has_phone: boolean | null;
  quality_filter: string | null;
  sort_by: string;
  natural_explanation: string;
}

export interface AISearchResponse {
  intent: AISearchIntent;
  total_count: number;
  avg_lead_price: number;
  preview: PricedLead[];
  query: SearchQuery;
}

export interface OrderSummary {
  id: number;
  industry: string;
  state: string;
  city: string | null;
  quantity: number;
  amount_dollars: number;
  created_at: string;
  stripe_session_id: string;
}

export interface OrdersResponse {
  purchases: OrderSummary[];
}

export interface SubscriptionStatus {
  subscribed: boolean;
  status?: string;
  plan?: string;
  leads_per_month?: number;
  credits_remaining?: number;
  current_period_end?: string;
  created_at?: string;
}

export interface SubscriptionDownload {
  industry: string;
  state: string;
  city: string | null;
  quantity: number;
  downloaded_at: string;
}

export interface SubscriptionHistory {
  downloads: SubscriptionDownload[];
}

// Bulk discount tiers — mirrors backend pricing.py
export const BULK_DISCOUNTS: { min: number; discount: number }[] = [
  { min: 10000, discount: 0.45 },
  { min: 5000, discount: 0.35 },
  { min: 1000, discount: 0.25 },
  { min: 500, discount: 0.18 },
  { min: 100, discount: 0.10 },
  { min: 1, discount: 0.0 },
];

export function getBulkDiscount(qty: number): number {
  return BULK_DISCOUNTS.find((t) => qty >= t.min)?.discount ?? 0;
}

export function calcTotal(avgPrice: number, quantity: number) {
  const discount = getBulkDiscount(quantity);
  const subtotal = avgPrice * quantity;
  const total = subtotal * (1 - discount);
  const perLead = quantity > 0 ? total / quantity : 0;
  return {
    discountPct: Math.round(discount * 100),
    subtotal,
    total: Math.max(total, 0.5),
    perLead,
  };
}
