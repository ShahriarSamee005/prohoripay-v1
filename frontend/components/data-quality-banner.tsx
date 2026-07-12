"use client";

import type { Meta, Provider, ProviderFeedStatus } from "@/lib/types";

const PROVIDER_LABELS: Record<Provider, string> = {
  bkash: "bKash",
  nagad: "Nagad",
  rocket: "Rocket",
};

interface DataQualityBannerProps {
  meta?: Meta | null;
  feedStatuses?: Partial<Record<Provider, ProviderFeedStatus>>;
}

/**
 * Renders nothing when all data is ok.
 * Shows a visible caution when degraded or stale — the frontend must never
 * present a confident conclusion on degraded data (Scenario C per contract.md).
 * Accepts either a global meta or per-provider live feed statuses (or both).
 */
export function DataQualityBanner({ meta, feedStatuses }: DataQualityBannerProps) {
  const degradedProviders = Object.entries(feedStatuses ?? {}) as [
    Provider,
    ProviderFeedStatus
  ][];

  const hasGlobalBanner = meta && meta.data_quality !== "ok";
  const hasProviderBanners = degradedProviders.length > 0;

  if (!hasGlobalBanner && !hasProviderBanners) return null;

  return (
    <div className="flex flex-col gap-2">
      {/* Global meta banner */}
      {hasGlobalBanner && (
        <GlobalBanner meta={meta!} />
      )}

      {/* Per-provider live feed banners */}
      {degradedProviders.map(([provider, status]) => (
        <ProviderFeedBanner key={provider} provider={provider} status={status} />
      ))}
    </div>
  );
}

function GlobalBanner({ meta }: { meta: Meta }) {
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

function ProviderFeedBanner({
  provider,
  status,
}: {
  provider: Provider;
  status: ProviderFeedStatus;
}) {
  const isStale = status.data_quality === "stale";
  const label = PROVIDER_LABELS[provider];
  const confPct = Math.round(status.confidence_modifier * 100);

  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-md border border-warning bg-surface-high px-4 py-3"
    >
      <span className="mt-0.5 text-warning text-title-sm shrink-0" aria-hidden>
        {isStale ? "⏱" : "⚠️"}
      </span>
      <div className="flex flex-col gap-0.5 flex-1 min-w-0">
        <p className="text-label-md text-primary">
          {label} feed {isStale ? "stale" : "degraded"} — confidence reduced
        </p>
        <p className="text-body-sm text-secondary">
          {label} data is {isStale ? "not updating" : "late or conflicting"}.{" "}
          Confidence for {label} figures is now{" "}
          <span className="text-warning font-semibold tabular-nums-bv">~{confPct}%</span>.
          {" "}Review before acting.
        </p>
      </div>
    </div>
  );
}
