"use client";

import { motion } from "framer-motion";
import type { Pool } from "@/lib/types";
import { PoolStatusChip } from "./pool-status-chip";

interface HeroCardProps {
  pools: Pool[];
  agentName: string;
  agentArea: string;
}

function fmt(n: number) {
  return n.toLocaleString("en-BD");
}

/**
 * Hero card per contract's "Hero framing" rules (compliance-critical):
 * - Shows Total Holdings ONLY labeled as a sum of separate, non-interchangeable pools.
 * - Always surfaces the constraining pool (lowest balance / critical/watch status).
 * - Never presents the total as a single spendable balance or health signal.
 * - Uses bg-brand-gradient per design.md magenta hero recipe.
 */
export function HeroCard({ pools, agentName, agentArea }: HeroCardProps) {
  const total = pools.reduce((s, p) => s + p.balance, 0);

  // Constraining pool: critical first, then watch, then the lowest balance
  const constraining =
    pools.find((p) => p.status === "critical") ??
    pools.find((p) => p.status === "watch") ??
    pools.reduce((a, b) => (a.balance < b.balance ? a : b));

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
        <p className="text-label-md opacity-80">
          Total Holdings
        </p>
        <p className="text-display-lg tabular-nums-bv leading-none">
          ৳{fmt(total)}
        </p>
        {/* Compliance disclaimer — always visible */}
        <p className="mt-1 text-body-sm opacity-70">
          Sum of separate, non-interchangeable pools · not a single spendable balance
        </p>
      </div>

      {/* Constraining pool — must always be shown beside the total */}
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
        <ConstraintChip status={constraining.status} />
      </div>
    </motion.div>
  );
}

function ConstraintChip({ status }: { status: Pool["status"] }) {
  const map = {
    critical: { label: "⚠ Physical cash critical", bg: "bg-white/20 text-on-brand border border-white/30" },
    watch: { label: "● Needs attention", bg: "bg-white/15 text-on-brand border border-white/20" },
    healthy: { label: "✓ Healthy", bg: "bg-white/15 text-on-brand border border-white/20" },
  } as const;
  const cfg = map[status];
  return (
    <span
      className={`shrink-0 inline-flex items-center rounded-pill px-3 py-1 text-label-sm ${cfg.bg}`}
    >
      {cfg.label}
    </span>
  );
}
