"use client";

import { useState } from "react";

interface Props {
  onSearch: (query: string) => void;
  loading: boolean;
  naturalExplanation?: string;
}

const EXAMPLE_QUERIES = [
  "Roofing companies in Texas without a website",
  "HVAC businesses in Florida with email and phone",
  "High quality solar leads in California",
  "Small plumbing companies in Chicago area",
];

export default function AISearchBar({ onSearch, loading, naturalExplanation }: Props) {
  const [query, setQuery] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (query.trim()) onSearch(query.trim());
  }

  return (
    <div className="space-y-3">
      <form onSubmit={handleSubmit} className="flex gap-2">
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              if (query.trim()) onSearch(query.trim());
            }
          }}
          placeholder="Describe the leads you want... e.g. &quot;Roofing companies in Texas without a website&quot;"
          rows={2}
          className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500 resize-none"
        />
        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="self-end px-4 py-2 rounded-lg bg-violet-600 text-white text-sm font-semibold hover:bg-violet-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? (
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
              Searching…
            </span>
          ) : (
            "Search with AI"
          )}
        </button>
      </form>

      {/* AI explanation banner */}
      {naturalExplanation && !loading && (
        <div className="flex items-start gap-2 bg-violet-50 border border-violet-200 rounded-lg px-3 py-2 text-sm text-violet-800">
          <span className="text-violet-500 mt-0.5 shrink-0">✦</span>
          <span>
            <span className="font-medium">AI understood: </span>
            {naturalExplanation}
          </span>
        </div>
      )}

      {/* Example queries */}
      {!naturalExplanation && !loading && (
        <div className="flex flex-wrap gap-2">
          <span className="text-xs text-slate-400 mt-0.5">Try:</span>
          {EXAMPLE_QUERIES.map((ex) => (
            <button
              key={ex}
              onClick={() => {
                setQuery(ex);
                onSearch(ex);
              }}
              className="text-xs px-2 py-1 rounded-full bg-slate-100 text-slate-600 hover:bg-violet-100 hover:text-violet-700 transition-colors"
            >
              {ex}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
