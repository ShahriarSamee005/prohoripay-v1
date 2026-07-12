"use client";

import Link from "next/link";
import Image from "next/image";
import { motion } from "framer-motion";
import type { Pool } from "@/lib/types";

const PROVIDER_META: Record<
  string,
  { label: string; bg: string; glow: string; banner: string }
> = {
  bkash: {
    label: "bKash",
    bg: "linear-gradient(160deg, #E3106D 0%, #8a0040 100%)",
    glow: "rgba(227,16,109,0.55)",
    banner: "/icons/bkash.png",
  },
  nagad: {
    label: "Nagad",
    bg: "linear-gradient(160deg, #F47920 0%, #a84f0f 100%)",
    glow: "rgba(244,121,32,0.55)",
    banner: "/icons/nagad.png",
  },
  rocket: {
    label: "Rocket",
    bg: "linear-gradient(160deg, #8B2BE2 0%, #4e1882 100%)",
    glow: "rgba(139,43,226,0.55)",
    banner: "/icons/rocket.png",
  },
};

interface ProviderCardRowProps {
  pools: Pool[];
}

export function ProviderCardRow({ pools }: ProviderCardRowProps) {
  const providerPools = pools.filter((p) => p.kind === "provider_emoney");

  return (
    <div className="flex flex-col gap-2">
      <h2 className="text-title-sm text-secondary px-1">Providers</h2>
      <div className="grid grid-cols-3 gap-3">
        {providerPools.map((pool, i) => (
          <ProviderCard key={pool.pool_id} pool={pool} index={i} />
        ))}
      </div>
    </div>
  );
}

function ProviderCard({ pool, index }: { pool: Pool; index: number }) {
  const meta = PROVIDER_META[pool.provider ?? ""] ?? {
    label: pool.label,
    bg: "linear-gradient(160deg, var(--bv-surface-high), var(--bv-surface))",
    glow: "var(--bv-brand-glow)",
    banner: "",
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.32, delay: index * 0.09, ease: "easeOut" }}
    >
      <Link
        href={`/provider/${pool.provider}`}
        className="group block relative overflow-hidden rounded-xl focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
        style={{
          boxShadow: `0 0 0 1px rgba(255,255,255,0.08), 0 8px 24px -8px ${meta.glow}`,
        }}
      >
        {/* Animated glow ring on hover */}
        <motion.div
          className="absolute inset-0 rounded-xl pointer-events-none z-10"
          initial={{ opacity: 0 }}
          whileHover={{ opacity: 1 }}
          transition={{ duration: 0.2 }}
          style={{
            boxShadow: `0 0 0 2px rgba(255,255,255,0.25), 0 0 28px 6px ${meta.glow}`,
          }}
        />

        {/* Background gradient */}
        <div
          className="absolute inset-0"
          style={{ background: meta.bg }}
        />

        {/* Icon only — centered, larger */}
        <div className="relative z-[2] flex items-center justify-center py-7 px-2 min-h-[110px]">
          {meta.banner && (
            <motion.div
              whileHover={{ scale: 1.08 }}
              transition={{ type: "spring", stiffness: 300, damping: 20 }}
              className="w-20 h-20 rounded-2xl overflow-hidden flex items-center justify-center"
              style={{
                background: "rgba(255,255,255,0.15)",
                backdropFilter: "blur(4px)",
                boxShadow: `0 6px 24px ${meta.glow}`,
              }}
            >
              <Image
                src={meta.banner}
                alt={meta.label}
                width={80}
                height={80}
                className="object-contain w-16 h-16"
                unoptimized
              />
            </motion.div>
          )}
        </div>
      </Link>
    </motion.div>
  );
}

