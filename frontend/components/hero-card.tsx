"use client";

import { motion } from "framer-motion";
import type { Pool, Forecast } from "@/lib/types";
import { PoolStatusChip } from "./pool-status-chip";

interface HeroCardProps {
  pools: Pool[];
  forecasts?: Forecast[];
  agentName: string;
  agentArea: string;
}

function fmt(n: number) {
  return n.toLocaleString("en-BD");
}

/**
 * Hero framing (contract §Hero framing):
 * - Total Holdings = sum of separate, non-interchangeable pools (never "spendable").
 * - Constraining pool = pool with SOONEST minutes_to_depletion when forecast is
 *   available, else lowest-headroom / critical/watch pool.
 * - Status chip surfaces forecast-derived countdown when present.
 */
function getConstrainingPool(pools: Pool[], forecasts?: Forecast[]): Pool {
  if (forecasts && forecasts.length > 0) {
    const depleting = forecasts
      .filter((f) => f.minutes_to_depletion != null)
      .sort((a, b) => a.minutes_to_depletion! - b.minutes_to_depletion!);
    if (depleting.length > 0) {
      const soonest = depleting[0];
      const match = pools.find((p) => p.pool_id === soonest.pool_id);
      if (match) return match;
    }
    // All filling/stable — show lowest balance pool
    return pools.reduce((a, b) => (a.balance < b.balance ? a : b));
  }
  // Fallback: status-based, then lowest balance
  return (
    pools.find((p) => p.status === "critical") ??
    pools.find((p) => p.status === "watch") ??
    pools.reduce((a, b) => (a.balance < b.balance ? a : b))
  );
}

export function HeroCard({
  pools,
  forecasts,
  agentName,
  agentArea,
}: HeroCardProps) {
  const total = pools.reduce((s, p) => s + p.balance, 0);
  const constraining = getConstrainingPool(pools, forecasts);
  const constrainingForecast = forecasts?.find(
    (f) => f.pool_id === constraining.pool_id,
  );

  return (
    <motion.div
      className="bg-brand-gradient text-on-brand rounded-xl shadow-brand-glow p-5 flex flex-col gap-4"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
    >
      {/* Agent identity */}
      <div className="flex items-center justify-between gap-2">
        <div>
          <p className="text-label-md opacity-80">Agent</p>
          <p className="text-title-lg">{agentName}</p>
          <p className="text-body-sm opacity-70">{agentArea}</p>
        </div>
      </div>

      {/* Total holdings — compliance label is mandatory */}
      <div>
        <p className="text-label-md opacity-80">Total Holdings</p>
        <p className="text-display-lg tabular-nums-bv leading-none">
          ৳{fmt(total)}
        </p>
        <p className="mt-1 text-body-sm opacity-70">
          Sum of separate, non-interchangeable pools · not a single spendable
          balance
        </p>
      </div>

      {/* Constraining pool — always shown beside the total */}
      <div className="rounded-lg bg-white/10 backdrop-blur-sm px-4 py-3 flex items-center justify-between gap-3">
        <div>
          <p className="text-label-sm opacity-80">Constraining pool</p>
          <p className="text-title-md">
            {constraining.label}
            <span className="ml-2 tabular-nums-bv">
              ৳{fmt(constraining.balance)}
            </span>
          </p>
        </div>
        <ConstraintChip pool={constraining} forecast={constrainingForecast} />
      </div>
    </motion.div>
  );
}

function ConstraintChip({
  pool,
  forecast,
}: {
  pool: Pool;
  forecast?: Forecast;
}) {
  const mins = forecast?.minutes_to_depletion;

  let label: string;
  if (mins != null) {
    label = `⚠ ~${mins} min`;
  } else if (forecast?.trend === "filling") {
    label = "↑ Growing";
  } else if (pool.status === "critical") {
    label = "⚠ Critical";
  } else if (pool.status === "watch") {
    label = "● Needs attention";
  } else {
    label = "✓ Healthy";
  }

  return (
    <span className="shrink-0 inline-flex items-center rounded-pill px-3 py-1 text-label-sm bg-white/20 text-on-brand border border-white/30">
      {label}
    </span>
  );
}
