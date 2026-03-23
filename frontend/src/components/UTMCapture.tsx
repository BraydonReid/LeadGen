"use client";
import { captureUTM } from "@/lib/utm";
import { useEffect } from "react";

/** Drop this anywhere in the layout — captures UTM params silently on mount. */
export default function UTMCapture() {
  useEffect(() => { captureUTM(); }, []);
  return null;
}
