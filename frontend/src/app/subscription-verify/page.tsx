"use client";

import { useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Suspense } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function VerifyInner() {
  const params = useSearchParams();
  const router = useRouter();
  const token = params.get("token");

  const [status, setStatus] = useState<"verifying" | "success" | "error">("verifying");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setStatus("error");
      setError("No token found in link. Please request a new sign-in link.");
      return;
    }

    async function verify() {
      try {
        const res = await fetch(
          `${API_BASE}/api/subscription/auth/verify?token=${encodeURIComponent(token!)}`,
        );
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error((data as { detail?: string }).detail ?? "Link expired or already used.");
        }
        const { session_token, email } = await res.json();
        localStorage.setItem("leadgen_sub_session", session_token);
        localStorage.setItem("leadgen_buyer_email", email);
        setStatus("success");
        setTimeout(() => router.push("/my-subscription"), 1200);
      } catch (err) {
        setStatus("error");
        setError(err instanceof Error ? err.message : "Verification failed.");
      }
    }

    verify();
  }, [token, router]);

  if (status === "verifying") {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center">
          <div className="w-10 h-10 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-slate-600 font-medium">Signing you in…</p>
        </div>
      </div>
    );
  }

  if (status === "success") {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center">
          <div className="w-12 h-12 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-6 h-6 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <p className="text-slate-900 font-bold text-lg">Signed in!</p>
          <p className="text-slate-500 text-sm mt-1">Redirecting to your subscription…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center px-4">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-8 w-full max-w-sm text-center">
        <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <svg className="w-6 h-6 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </div>
        <h2 className="text-lg font-black text-slate-900 mb-2">Link expired</h2>
        <p className="text-slate-500 text-sm mb-6">{error}</p>
        <a
          href="/my-subscription"
          className="block w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 rounded-xl text-sm transition-all"
        >
          Request a New Link →
        </a>
      </div>
    </div>
  );
}

export default function SubscriptionVerifyPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin" />
      </div>
    }>
      <VerifyInner />
    </Suspense>
  );
}
