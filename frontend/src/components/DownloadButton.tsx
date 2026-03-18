"use client";

import { downloadUrl } from "@/lib/api";

export default function DownloadButton({ sessionId }: { sessionId: string }) {
  const handleClick = () => {
    window.location.href = downloadUrl(sessionId);
  };

  return (
    <button
      onClick={handleClick}
      className="bg-blue-600 hover:bg-blue-700 text-white font-bold px-8 py-3 rounded-xl text-lg transition"
    >
      Download CSV
    </button>
  );
}
