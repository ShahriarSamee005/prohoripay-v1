import { notFound } from "next/navigation";
import Image from "next/image";
import Link from "next/link";
import { getAgent, getPools, getTransactions, getForecast } from "@/lib/api";
import type { Provider } from "@/lib/types";
import { ThemeToggle } from "@/components/theme-toggle";
import { ProviderLabel } from "@/components/provider-logo";
import { PoolStatusChip } from "@/components/pool-status-chip";
import { TransactionList } from "@/components/transaction-list";
import { DataQualityBanner } from "@/components/data-quality-banner";
import { ForecastPanel } from "@/components/forecast-panel";

export const dynamic = "force-dynamic";

const VALID_PROVIDERS: Provider[] = ["bkash", "nagad", "rocket"];

interface Props {
  params: Promise<{ id: string }>;
}

const PROVIDER_META: Record<
  string,
  { bg: string; glow: string; banner: string; badge: string; label: string }
> = {
  bkash: {
    bg: "linear-gradient(135deg, #E3106D 0%, #7d0038 100%)",
    glow: "rgba(227,16,109,0.45)",
    banner: "/icons/bkash.png",
    badge: "/icons/bkash2.png",
    label: "bKash",
  },
  nagad: {
    bg: "linear-gradient(135deg, #F47920 0%, #8a3f08 100%)",
    glow: "rgba(244,121,32,0.45)",
    banner: "/icons/nagad.png",
    badge: "/icons/nagad2.png",
    label: "Nagad",
  },
  rocket: {
    bg: "linear-gradient(135deg, #8B2BE2 0%, #3e0f82 100%)",
    glow: "rgba(139,43,226,0.45)",
    banner: "/icons/rocket.png",
    badge: "/icons/rocket2.png",
    label: "Rocket",
  },
};

function fmt(n: number) {
  return n.toLocaleString("en-BD");
}

export default async function ProviderDetailPage({ params }: Props) {
  const { id } = await params;

  if (!VALID_PROVIDERS.includes(id as Provider)) notFound();
  const provider = id as Provider;

  const [agent, poolsResp, txnsResp, forecastsResp] = await Promise.all([
    getAgent(),
    getPools(),
    getTransactions({ limit: 20, provider }),
    getForecast().catch(() => null),
  ]);

  const pool = poolsResp.pools.find((p) => p.provider === provider);
  if (!pool) notFound();

  const { transactions, meta: txnMeta } = txnsResp;
  const forecasts = forecastsResp?.forecasts ?? [];
  const forecastMeta = forecastsResp?.meta ?? txnMeta;
  const forecast = forecasts.find((f) => f.pool_id === provider);

  const meta = PROVIDER_META[provider];

  const cashIn = transactions.filter((t) => t.txn_type === "cash_in");
  const cashOut = transactions.filter((t) => t.txn_type === "cash_out");
  const cashInTotal = cashIn.reduce((s, t) => s + t.amount, 0);
  const cashOutTotal = cashOut.reduce((s, t) => s + t.amount, 0);

  return (
    <main className="min-h-dvh bg-background">
      {/* Hero banner */}
      <div
        className="relative overflow-hidden"
        style={{
          background: meta.bg,
          boxShadow: `0 8px 40px -8px ${meta.glow}`,
        }}
      >
        {/* Subtle dot-grid overlay */}
        <div
          className="absolute inset-0 opacity-10 pointer-events-none"
          style={{
            backgroundImage: "radial-gradient(circle, rgba(255,255,255,0.4) 1px, transparent 1px)",
            backgroundSize: "24px 24px",
          }}
        />

        <div className="relative z-10 px-4 pt-10 pb-8">
          <div className="mx-auto max-w-2xl">
            {/* Back + theme toggle row */}
            <div className="flex items-center justify-between gap-4 mb-6">
              <Link
                href="/"
                className="flex items-center gap-1.5 text-label-md rounded-lg px-2.5 py-1.5 transition-colors duration-fast"
                style={{
                  color: "rgba(255,255,255,0.85)",
                  background: "rgba(255,255,255,0.12)",
                  backdropFilter: "blur(8px)",
                }}
              >
                ← Dashboard
              </Link>
              <ThemeToggle />
            </div>

            {/* Provider identity */}
            <div className="flex items-center gap-5">
              <div
                className="size-20 rounded-2xl overflow-hidden flex items-center justify-center shrink-0"
                style={{
                  background: "rgba(255,255,255,0.18)",
                  backdropFilter: "blur(8px)",
                  boxShadow: `0 8px 24px ${meta.glow}`,
                }}
              >
                <Image
                  src={meta.banner}
                  alt={meta.label}
                  width={64}
                  height={64}
                  className="object-contain w-14 h-14"
                  unoptimized
                />
              </div>
              <div>
                <p className="text-body-sm" style={{ color: "rgba(255,255,255,0.65)" }}>
                  {agent.name} · {agent.area}
                </p>
                <p
                  className="text-headline-md font-bold mt-0.5"
                  style={{ color: "rgba(255,255,255,0.96)" }}
                >
                  <ProviderLabel provider={provider} />
                </p>
                <div className="mt-1.5 flex items-center gap-2">
                  <PoolStatusChip status={pool.status} />
                  <span
                    className="text-body-sm"
                    style={{ color: "rgba(255,255,255,0.6)" }}
                  >
                    e-Money pool · separate balance
                  </span>
                </div>
              </div>
            </div>

            {/* Balance + quick stats */}
            <div className="mt-6 grid grid-cols-3 gap-3">
              <StatTile
                label="e-Money Balance"
                value={`৳${fmt(pool.balance)}`}
                highlight
              />
              <StatTile label="Cash In (recent)" value={`৳${fmt(cashInTotal)}`} up />
              <StatTile label="Cash Out (recent)" value={`৳${fmt(cashOutTotal)}`} down />
            </div>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="mx-auto max-w-2xl px-4 py-6 flex flex-col gap-6">
        <DataQualityBanner meta={txnMeta} />

        {/* Forecast */}
        {forecast ? (
          <ForecastPanel forecast={forecast} meta={forecastMeta} />
        ) : (
          <section
            className="rounded-xl border border-default px-5 py-6"
            style={{ background: "var(--bv-surface)" }}
          >
            <p className="text-label-md text-tertiary">Forecast unavailable</p>
            <p className="text-body-sm text-tertiary mt-1">
              No forecast data returned for this pool.
            </p>
          </section>
        )}

        {/* Recent transactions */}
        <section className="flex flex-col gap-2">
          <div className="flex items-center justify-between px-1">
            <h2 className="text-title-sm text-secondary">Recent Transactions</h2>
            <span className="text-label-sm text-tertiary tabular-nums-bv">
              {transactions.length} shown
            </span>
          </div>
          <div
            className="rounded-xl border border-default overflow-hidden shadow-card"
            style={{ background: "var(--bv-surface)" }}
          >
            <TransactionList transactions={transactions} />
          </div>
        </section>

        <footer className="text-body-sm text-tertiary text-center pb-4">
          Advisory only · no financial decisions are made automatically
        </footer>
      </div>
    </main>
  );
}

function StatTile({
  label,
  value,
  highlight,
  up,
  down,
}: {
  label: string;
  value: string;
  highlight?: boolean;
  up?: boolean;
  down?: boolean;
}) {
  const arrowColor = up
    ? "rgba(255,255,255,0.55)"
    : down
      ? "rgba(255,255,255,0.55)"
      : undefined;

  return (
    <div
      className="rounded-xl px-3 py-3 flex flex-col gap-0.5"
      style={{
        background: highlight
          ? "rgba(255,255,255,0.22)"
          : "rgba(255,255,255,0.10)",
        backdropFilter: "blur(8px)",
        border: "1px solid rgba(255,255,255,0.15)",
      }}
    >
      <p className="text-label-sm" style={{ color: "rgba(255,255,255,0.65)" }}>
        {label}
      </p>
      <p className="text-title-sm tabular-nums-bv font-bold" style={{ color: "rgba(255,255,255,0.95)" }}>
        {up && <span style={{ color: arrowColor }}>↑ </span>}
        {down && <span style={{ color: arrowColor }}>↓ </span>}
        {value}
      </p>
    </div>
  );
}
