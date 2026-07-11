import type { Forecast, ConfidenceFactors, Meta, ProjectionState } from "@/lib/types";
import { BurnDownChart } from "./burn-down-chart";
import { DataQualityBanner } from "./data-quality-banner";
import { ExplanationBlock } from "./explanation-block";

// ── Trend configuration ───────────────────────────────────────────────────────

const TREND_CONFIG = {
  accelerating: {
    label: "Accelerating drain",
    textClass: "text-danger",
    bgClass: "bg-danger",
    icon: "↗",
  },
  steady: {
    label: "Steady drain",
    textClass: "text-secondary",
    bgClass: "bg-surface-high",
    icon: "→",
  },
  easing: {
    label: "Drain easing",
    textClass: "text-success",
    bgClass: "bg-success",
    icon: "↘",
  },
  filling: {
    label: "Balance growing",
    textClass: "text-success",
    bgClass: "bg-success",
    icon: "↑",
  },
} as const;

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtDepletionTime(ts: string): string {
  const d = new Date(ts);
  return d.toLocaleTimeString("en-BD", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
    timeZone: "UTC",
  });
}

// ── Sub-components ────────────────────────────────────────────────────────────

function TrendChip({ trend }: { trend: Forecast["trend"] }) {
  const cfg = TREND_CONFIG[trend];
  return (
    <span
      className="inline-flex items-center gap-1 rounded-pill px-3 py-1 text-label-sm"
      style={{
        color: `var(--bv-${trend === "steady" ? "text-secondary" : trend === "accelerating" ? "danger" : "success"})`,
        background: `color-mix(in srgb, var(--bv-${trend === "accelerating" ? "danger" : trend === "steady" ? "text-secondary" : "success"}) 12%, transparent)`,
      }}
    >
      <span aria-hidden="true">{cfg.icon}</span>
      {cfg.label}
    </span>
  );
}

function FactorBar({
  label,
  value,
}: {
  label: string;
  value: number;
}) {
  const pct = Math.round(value * 100);
  const color =
    pct >= 70
      ? "var(--bv-success)"
      : pct >= 50
        ? "var(--bv-warning)"
        : "var(--bv-danger)";
  return (
    <div className="flex items-center gap-2">
      <span className="text-body-sm text-secondary w-28 shrink-0">{label}</span>
      <div className="flex-1 h-1.5 rounded-pill bg-surface-high overflow-hidden">
        <div
          className="h-full rounded-pill"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
      <span className="text-label-sm text-secondary tabular-nums-bv w-8 text-right">
        {pct}%
      </span>
    </div>
  );
}

function ConfidenceDetail({
  confidence,
  factors,
}: {
  confidence: number;
  factors: ConfidenceFactors;
}) {
  const pct = Math.round(confidence * 100);
  return (
    <details className="group">
      <summary className="cursor-pointer list-none select-none text-label-sm text-secondary hover:text-primary transition-colors duration-fast focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand rounded-sm">
        <span className="tabular-nums-bv">{pct}%</span> confidence{" "}
        <span className="text-tertiary group-open:hidden" aria-hidden="true">
          ⓘ
        </span>
        <span className="text-tertiary hidden group-open:inline" aria-hidden="true">
          ▴
        </span>
      </summary>
      <div className="mt-2 bg-surface-high rounded-lg p-3 flex flex-col gap-2">
        <p className="text-label-sm text-tertiary">Confidence breakdown</p>
        <FactorBar label="Volatility" value={1 - factors.volatility} />
        <FactorBar label="Sample size" value={factors.sample_size} />
        <FactorBar label="Data freshness" value={factors.data_freshness} />
      </div>
    </details>
  );
}

// ── Projection-state display ──────────────────────────────────────────────────

function DepletionSection({ forecast }: { forecast: Forecast }) {
  const { projection_state, minutes_to_depletion, projected_depletion_ts, confidence, confidence_factors } = forecast;

  if (projection_state === "projected" && minutes_to_depletion != null && projected_depletion_ts != null) {
    return (
      <div className="flex flex-col gap-2">
        <p className="text-label-sm text-secondary uppercase tracking-wide">Estimated depletion</p>
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <p className="text-display-sm tabular-nums-bv text-danger leading-none">
              ~{minutes_to_depletion} min
            </p>
            <p className="text-body-sm text-secondary tabular-nums-bv mt-1">
              projected {fmtDepletionTime(projected_depletion_ts)}
            </p>
          </div>
          <ConfidenceDetail confidence={confidence} factors={confidence_factors} />
        </div>
      </div>
    );
  }

  if (projection_state === "filling") {
    return (
      <div className="flex flex-col gap-2">
        <p className="text-label-sm text-secondary uppercase tracking-wide">Estimated depletion</p>
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <p className="text-title-lg text-success">
            Balance stable or growing — no shortage projected
          </p>
          <ConfidenceDetail confidence={confidence} factors={confidence_factors} />
        </div>
      </div>
    );
  }

  if (projection_state === "insufficient_data" || projection_state === "intermittent") {
    const detail =
      projection_state === "insufficient_data"
        ? "Too few transactions to build a reliable drain model."
        : "Activity is clumpy or bursty — drain rate estimate is unreliable.";
    return (
      <div className="flex flex-col gap-2">
        <p className="text-label-sm text-secondary uppercase tracking-wide">Estimated depletion</p>
        <div
          className="rounded-lg px-4 py-3 flex flex-col gap-2 border"
          style={{
            background: "color-mix(in srgb, var(--bv-warning) 8%, transparent)",
            borderColor: "color-mix(in srgb, var(--bv-warning) 30%, transparent)",
          }}
        >
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div className="flex items-center gap-2">
              <span
                className="text-label-sm font-medium"
                style={{ color: "var(--bv-warning)" }}
                aria-hidden="true"
              >
                ◐
              </span>
              <p className="text-title-md" style={{ color: "var(--bv-warning)" }}>
                Monitoring — limited{projection_state === "intermittent" ? "/intermittent" : ""} activity
              </p>
            </div>
            <ConfidenceDetail confidence={confidence} factors={confidence_factors} />
          </div>
          <p className="text-body-sm text-secondary">{detail}</p>
          <p
            className="text-label-sm"
            style={{ color: "var(--bv-warning)" }}
          >
            Low confidence — no reliable depletion estimate available
          </p>
        </div>
      </div>
    );
  }

  if (projection_state === "at_floor") {
    return (
      <div className="flex flex-col gap-2">
        <p className="text-label-sm text-secondary uppercase tracking-wide">Estimated depletion</p>
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <p className="text-title-lg text-danger">Balance at or below safety floor</p>
            <p className="text-body-sm text-secondary mt-1">
              Operations may be constrained — review immediately
            </p>
          </div>
          <ConfidenceDetail confidence={confidence} factors={confidence_factors} />
        </div>
      </div>
    );
  }

  // Fallback for any future projection_state value
  return (
    <div className="flex flex-col gap-2">
      <p className="text-label-sm text-secondary uppercase tracking-wide">Estimated depletion</p>
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <p className="text-body-md text-secondary">No depletion estimate available</p>
        <ConfidenceDetail confidence={confidence} factors={confidence_factors} />
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

interface ForecastPanelProps {
  forecast: Forecast;
  meta: Meta;
}

export function ForecastPanel({ forecast, meta }: ForecastPanelProps) {
  return (
    <section className="flex flex-col gap-3">
      {/* Section header + trend chip */}
      <div className="flex items-center gap-2 flex-wrap px-1">
        <h2 className="text-title-sm text-secondary">Liquidity Forecast</h2>
        <TrendChip trend={forecast.trend} />
      </div>

      {/* Degraded-data banner for the forecast meta */}
      <DataQualityBanner meta={meta} />

      <div className="bg-surface border border-default rounded-xl shadow-card p-5 flex flex-col gap-5">
        {/* ── Projection state — countdown / safe / low-confidence / at-floor ── */}
        <DepletionSection forecast={forecast} />

        {/* ── Burn-down chart ── */}
        <BurnDownChart forecast={forecast} />

        {/* ── Recommended action ── */}
        <div className="flex flex-col gap-1.5 border-t border-default pt-4">
          <p className="text-label-sm text-secondary">Suggested action</p>
          <p className="text-body-md text-primary">{forecast.recommended_action}</p>
          <p className="text-body-sm text-tertiary">
            Advisory only — no action is taken automatically
          </p>
        </div>

        {/* ── Evidence (authoritative — unchanged) ── */}
        <div className="flex flex-col gap-2">
          <p className="text-label-sm text-secondary">Evidence</p>
          <ul className="flex flex-col gap-1.5" role="list">
            {forecast.evidence.map((item, i) => (
              <li key={i} className="flex items-start gap-2 text-body-sm text-primary">
                <span className="text-brand shrink-0 mt-0.5" aria-hidden="true">
                  •
                </span>
                {item}
              </li>
            ))}
          </ul>
        </div>

        {/* ── Phase 6 — Plain-language explanation (additive; sits alongside evidence) ── */}
        <ExplanationBlock kind="forecast" id={forecast.pool_id} />
      </div>
    </section>
  );
}
