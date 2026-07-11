"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import type { Pool } from "@/lib/types";
import { ProviderLogo } from "./provider-logo";
import { PoolStatusChip } from "./pool-status-chip";

interface ProviderCardRowProps {
  pools: Pool[];
}

function fmt(n: number) {
  return n.toLocaleString("en-BD");
}

/** One card per provider in a horizontal row, each clickable → /provider/[id]. */
export function ProviderCardRow({ pools }: ProviderCardRowProps) {
  const providerPools = pools.filter((p) => p.kind === "provider_emoney");

  return (
    <div className="flex flex-col gap-2">
      <h2 className="text-title-sm text-secondary px-1">Providers</h2>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {providerPools.map((pool, i) => (
          <ProviderCard key={pool.pool_id} pool={pool} index={i} />
        ))}
      </div>
    </div>
  );
}

function ProviderCard({ pool, index }: { pool: Pool; index: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.08, ease: "easeOut" }}
    >
      <Link
        href={`/provider/${pool.provider}`}
        className="group block bg-surface border border-default rounded-lg shadow-card p-4
                   hover:bg-surface-high transition-colors duration-fast
                   focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
      >
        <div className="flex items-center gap-3 mb-3">
          <ProviderLogo provider={pool.provider!} size="sm" />
          <p className="text-title-sm text-primary">{pool.label}</p>
        </div>
        <p className="text-display-sm tabular-nums-bv text-primary leading-none mb-2">
          ৳{fmt(pool.balance)}
        </p>
        <div className="flex items-center justify-between">
          <PoolStatusChip status={pool.status} />
          <span className="text-label-sm text-brand group-hover:underline">
            Details →
          </span>
        </div>
      </Link>
    </motion.div>
  );
}
