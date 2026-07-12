"use client";

import { motion } from "framer-motion";
import type { Pool } from "@/lib/types";
import { ProviderLogo } from "./provider-logo";
import { PoolStatusChip } from "./pool-status-chip";

interface PoolBreakdownProps {
  pools: Pool[];
}

function fmt(n: number) {
  return n.toLocaleString("en-BD");
}

/**
 * Breakdown directly beneath the hero: physical cash + each provider with
 * logo/label and balance. Pools listed in order: physical_cash first, then
 * provider pools. Each pool has a status chip.
 */
export function PoolBreakdown({ pools }: PoolBreakdownProps) {
  const physical = pools.find((p) => p.kind === "physical_cash");
  const providers = pools.filter((p) => p.kind === "provider_emoney");

  return (
    <div className="flex flex-col gap-2">
      <h2 className="text-title-sm text-secondary px-1">Balance Breakdown</h2>
      <div className="bg-surface border border-default rounded-lg shadow-card overflow-hidden">
        {physical && (
          <PoolRow pool={physical} index={0} />
        )}
        {providers.map((pool, i) => (
          <PoolRow key={pool.pool_id} pool={pool} index={i + 1} />
        ))}
      </div>
    </div>
  );
}

function PoolRow({ pool, index }: { pool: Pool; index: number }) {
  return (
    <motion.div
      className="flex items-center justify-between gap-3 px-4 py-3 border-b border-default last:border-b-0"
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.25, delay: index * 0.06, ease: "easeOut" }}
    >
      <div className="flex items-center gap-3 min-w-0">
        {pool.kind === "physical_cash" ? (
          <CashIcon />
        ) : (
          <ProviderLogo provider={pool.provider!} size="sm" />
        )}
        <div className="min-w-0">
          <p className="text-title-sm text-primary truncate">{pool.label}</p>
          <p className="text-body-sm text-tertiary">
            {pool.kind === "physical_cash" ? "Shared drawer" : "e-Money"}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-3 shrink-0">
        <p className="text-title-md tabular-nums-bv text-primary">
          <motion.span
            key={pool.balance}
            initial={{ opacity: 0.5, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2 }}
          >
            ৳{fmt(pool.balance)}
          </motion.span>
        </p>
        <PoolStatusChip status={pool.status} />
      </div>
    </motion.div>
  );
}

function CashIcon() {
  return (
    <span className="inline-flex shrink-0 size-8 items-center justify-center rounded-pill bg-surface-high text-secondary text-label-sm">
      ৳
    </span>
  );
}
