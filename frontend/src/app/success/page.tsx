"use client";

import { downloadUrl, reportLeads } from "@/lib/api";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

function ReportSection({ sessionId }: { sessionId: string }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [creditCode, setCreditCode] = useState<string | null>(null);
  const [creditAmount, setCreditAmount] = useState<number>(0);
  const [errMsg, setErrMsg] = useState<string | null>(null);

  const handleSubmit = async () => {
    setStatus("loading");
    setErrMsg(null);
    try {
      const res = await reportLeads(sessionId, reason);
      setCreditCode(res.credit_code);
      setCreditAmount(res.discount_amount_dollars);
      setStatus("done");
    } catch (e: unknown) {
      setErrMsg(e instanceof Error ? e.message : "Something went wrong");
      setStatus("error");
    }
  };

  if (status === "done" && creditCode) {
    return (
      <div className="mt-6 pt-6 border-t border-slate-100">
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 text-left">
          <p className="text-sm font-bold text-emerald-800 mb-1">
            Store credit issued — ${creditAmount.toFixed(2)} off your next order
          </p>
          <p className="text-xs text-emerald-700 mb-3">Enter this code at checkout:</p>
          <div className="flex items-center gap-2">
            <code className="flex-1 bg-white border border-emerald-300 rounded-lg px-3 py-2 text-sm font-mono font-bold text-emerald-900 tracking-wider">
              {creditCode}
            </code>
            <button
              onClick={() => navigator.clipboard.writeText(creditCode)}
              className="text-xs bg-emerald-600 hover:bg-emerald-700 text-white px-3 py-2 rounded-lg transition-colors"
            >
              Copy
            </button>
          </div>
          <p className="text-xs text-emerald-600 mt-2">
            Credit is single-use and never expires.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="mt-6 pt-6 border-t border-slate-100">
      {!open ? (
        <button
          onClick={() => setOpen(true)}
          className="text-sm text-slate-400 hover:text-slate-600 transition-colors"
        >
          Found bad leads? Report them → get store credit
        </button>
      ) : (
        <div className="text-left">
          <p className="text-sm font-semibold text-slate-700 mb-2">Report bad leads</p>
          <p className="text-xs text-slate-500 mb-3">
            We&apos;ll issue up to 10% store credit automatically — no questions asked.
          </p>
          <textarea
            rows={3}
            placeholder="Briefly describe the issue (e.g. disconnected numbers, wrong industry, closed businesses)"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            className="w-full text-sm border border-slate-200 rounded-xl px-3 py-2 mb-3 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
          />
          {errMsg && <p className="text-red-600 text-xs mb-2">{errMsg}</p>}
          <div className="flex gap-2">
            <button
              onClick={handleSubmit}
              disabled={status === "loading"}
              className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-semibold py-2 rounded-xl transition-colors"
            >
              {status === "loading" ? "Submitting…" : "Submit & Get Credit"}
            </button>
            <button
              onClick={() => setOpen(false)}
              className="text-sm text-slate-400 hover:text-slate-600 px-3"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function SuccessContent() {
  const searchParams = useSearchParams();
  const sessionId = searchParams.get("session_id");
  const [status, setStatus] = useState<"polling" | "ready" | "error">("polling");
  const [attempts, setAttempts] = useState(0);

  useEffect(() => {
    if (!sessionId) { setStatus("error"); return; }

    const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    const MAX = 24; // 24 × 2.5s = 60 seconds total
    let attempt = 0;

    const timer = setInterval(async () => {
      attempt++;
      setAttempts(attempt);
      try {
        const res = await fetch(
          `${API_BASE}/api/download?session_id=${encodeURIComponent(sessionId)}`,
          { method: "HEAD" }
        );
        if (res.ok) { setStatus("ready"); clearInterval(timer); return; }
      } catch { /* continue polling */ }
      if (attempt >= MAX) { setStatus("error"); clearInterval(timer); }
    }, 2500);

    return () => clearInterval(timer);
  }, [sessionId]);

  if (!sessionId) {
    return (
      <div className="text-center py-24">
        <p className="text-red-600">Invalid session. Please contact support.</p>
        <Link href="/shop" className="text-blue-600 mt-4 inline-block">← Back to shop</Link>
      </div>
    );
  }

  return (
    <div className="max-w-lg mx-auto py-24 px-6">
      <div className="bg-white rounded-3xl shadow-lg border border-slate-100 overflow-hidden">
        {status === "polling" && (
          <div className="p-10 text-center">
            <div className="w-16 h-16 bg-blue-50 rounded-full flex items-center justify-center mx-auto mb-6">
              <svg className="w-8 h-8 text-blue-600 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            </div>
            <h1 className="text-2xl font-bold text-slate-900 mb-2">Payment confirmed!</h1>
            <p className="text-slate-500 mb-6">Preparing your download…</p>
            <div className="w-full bg-slate-100 rounded-full h-2">
              <div
                className="bg-blue-500 h-2 rounded-full transition-all duration-500"
                style={{ width: `${Math.min((attempts / 24) * 100, 90)}%` }}
              />
            </div>
          </div>
        )}

        {status === "ready" && (
          <div className="p-10 text-center">
            <div className="w-16 h-16 bg-emerald-50 rounded-full flex items-center justify-center mx-auto mb-6">
              <svg className="w-8 h-8 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h1 className="text-2xl font-bold text-slate-900 mb-2">Your leads are ready!</h1>
            <p className="text-slate-500 mb-8">Click below to download your CSV file.</p>
            <a
              href={downloadUrl(sessionId)}
              className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white font-bold px-8 py-4 rounded-xl text-lg transition-all hover:scale-105"
              download
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              Download CSV
            </a>
            <p className="text-xs text-slate-400 mt-4">
              Bookmark this page — you can re-download using this link anytime.
            </p>
            <ReportSection sessionId={sessionId} />
            <div className="mt-4">
              <Link href="/shop" className="text-blue-600 text-sm hover:underline">
                ← Buy more leads
              </Link>
            </div>
          </div>
        )}

        {status === "error" && (
          <div className="p-10 text-center">
            <div className="w-16 h-16 bg-amber-50 rounded-full flex items-center justify-center mx-auto mb-6">
              <svg className="w-8 h-8 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
              </svg>
            </div>
            <h1 className="text-xl font-bold text-slate-900 mb-2">Taking longer than expected</h1>
            <p className="text-slate-500 text-sm mb-6">
              Your payment was processed. Try downloading directly or retry in a moment.
            </p>
            <div className="flex flex-col gap-3">
              <a
                href={downloadUrl(sessionId)}
                className="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 rounded-xl transition-all"
              >
                Try Download
              </a>
              <button
                onClick={() => { setStatus("polling"); setAttempts(0); }}
                className="bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold py-3 rounded-xl transition-all"
              >
                Retry
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function SuccessPage() {
  return (
    <div className="bg-slate-50 min-h-screen">
      <Suspense fallback={<div className="py-24 text-center text-slate-400">Loading…</div>}>
        <SuccessContent />
      </Suspense>
    </div>
  );
}
