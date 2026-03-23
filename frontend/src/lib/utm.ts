/**
 * UTM attribution tracking.
 *
 * Captures UTM params from the URL on first visit and persists them to
 * sessionStorage. Passed to /api/checkout so every purchase is tagged
 * with which ad/channel drove it.
 *
 * Uses sessionStorage (not localStorage) so a new session = fresh attribution.
 */

export interface UTMParams {
  utm_source?: string;
  utm_medium?: string;
  utm_campaign?: string;
  referrer?: string;
}

const KEY = "utm_params";

/** Call once on app load (e.g. in a top-level layout useEffect). */
export function captureUTM(): void {
  if (typeof window === "undefined") return;

  const params = new URLSearchParams(window.location.search);
  const source = params.get("utm_source");
  const medium = params.get("utm_medium");
  const campaign = params.get("utm_campaign");
  const referrer = document.referrer || undefined;

  // Only overwrite if this page load has UTM params
  if (source || medium || campaign) {
    const data: UTMParams = {};
    if (source) data.utm_source = source;
    if (medium) data.utm_medium = medium;
    if (campaign) data.utm_campaign = campaign;
    if (referrer) data.referrer = referrer;
    sessionStorage.setItem(KEY, JSON.stringify(data));
  } else if (!sessionStorage.getItem(KEY) && referrer) {
    // No UTM params but has referrer — store referrer only
    sessionStorage.setItem(KEY, JSON.stringify({ referrer }));
  }
}

/** Returns stored UTM params (or empty object if none). */
export function getUTM(): UTMParams {
  if (typeof window === "undefined") return {};
  try {
    const raw = sessionStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as UTMParams) : {};
  } catch {
    return {};
  }
}
