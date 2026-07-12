"use client";

import Image from "next/image";
import { motion } from "framer-motion";
import type { Pool } from "@/lib/types";
import type { Provider } from "@/lib/types";
import { PoolStatusChip } from "./pool-status-chip";

const BADGE: Record<Provider, string> = {
  bkash: "/icons/bkash2.png",
  nagad: "/icons/nagad2.png",
  rocket: "/icons/rocket2.png",
};

const PROVIDER_LABELS: Record<Provider, string> = {
  bkash: "bKash",
  nagad: "Nagad",
  rocket: "Rocket",
};

function fmt(n: number) {
  return n.toLocaleString("en-BD");
}

interface ProviderBalanceStripProps {
  pools: Pool[];
}

/**
 * Compact horizontal strip showing each provider's e-money balance and status.
 * Sits between the physical-cash hero card and the big logo provider row.
 */
export function ProviderBalanceStrip({ pools }: ProviderBalanceStripProps) {
  const providers = pools.filter((p) => p.kind === "provider_emoney");
  if (providers.length === 0) return null;

  return (
    <div className="flex flex-col gap-2">
      <h2 className="text-title-sm text-secondary px-1">e-Money Balances</h2>
      <div className="flex flex-col gap-3">
        {providers.map((pool, i) => (
          <ProviderBalanceCard key={pool.pool_id} pool={pool} index={i} />
        ))}
      </div>
    </div>
  );
}

function ProviderBalanceCard({ pool, index }: { pool: Pool; index: number }) {
  const provider = pool.provider as Provider;
  const badge = BADGE[provider];
  const label = PROVIDER_LABELS[provider] ?? pool.label;

  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.25, delay: index * 0.07, ease: "easeOut" }}
      className="bg-surface border border-default rounded-xl shadow-card px-4 py-3 flex items-center gap-4"
    >
      {/* Logo — transparent bg so it blends with the card surface */}
      <div className="size-11 shrink-0 flex items-center justify-center">
        <Image
          src={badge}
          alt={label}
          width={40}
          height={40}
          className="w-10 h-10 object-contain"
          unoptimized
        />
      </div>

      {/* Name */}
      <div className="flex-1 min-w-0">
        <p className="text-title-sm text-primary">{label}</p>
        <p className="text-label-sm text-tertiary">e-Money</p>
      </div>

      {/* Balance + status side by side */}
      <div className="flex items-center gap-2 shrink-0">
        <p className="text-title-md tabular-nums-bv text-primary leading-none">
          <motion.span
            key={pool.balance}
            initial={{ opacity: 0.4, y: -3 }}
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
