"use client";

import type { Meta } from "@/lib/types";

interface DataQualityBannerProps {
  meta: Meta | null;
}

/**
 * Renders nothing when data quality is "ok". Shows a visible caution when
 * degraded or stale — the frontend must never present a confident conclusion
 * on degraded data (Scenario C per contract.md).
 */
export function DataQualityBanner({ meta }: DataQualityBannerProps) {
  if (!meta || meta.data_quality === "ok") return null;

  const isStale = meta.data_quality === "stale";

  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-md border border-default bg-surface-high px-4 py-3"
    >
      <span className="mt-0.5 text-warning text-title-sm" aria-hidden>
        {isStale ? "⏱" : "⚠️"}
      </span>
      <div className="flex flex-col gap-0.5">
        <p className="text-label-md text-primary">
          {isStale ? "Data may be stale" : "Data feed degraded"}
        </p>
        <p className="text-body-sm text-secondary">
          {isStale
            ? "One or more provider feeds have not updated recently. Figures shown may not reflect current balances."
            : "A provider feed is late or conflicting. Shown balances require attention before acting."}
          {meta.confidence_modifier < 1 && (
            <> Confidence reduced to {Math.round(meta.confidence_modifier * 100)}%.</>
          )}
        </p>
      </div>
    </div>
  );
}
