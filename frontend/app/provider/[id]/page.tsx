import { notFound } from "next/navigation";
import Link from "next/link";
import { getAgent, getPools, getTransactions, getForecast } from "@/lib/api";
import type { Provider } from "@/lib/types";
import { ThemeToggle } from "@/components/theme-toggle";
import { ProviderLogo, ProviderLabel } from "@/components/provider-logo";
import { PoolStatusChip } from "@/components/pool-status-chip";
import { TransactionList } from "@/components/transaction-list";
import { DataQualityBanner } from "@/components/data-quality-banner";
import { ForecastPanel } from "@/components/forecast-panel";

export const dynamic = "force-dynamic";

const VALID_PROVIDERS: Provider[] = ["bkash", "nagad", "rocket"];

interface Props {
  params: Promise<{ id: string }>;
}

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
    // Graceful degradation — forecast endpoint may not exist in older backend builds
    getForecast().catch(() => null),
  ]);

  const pool = poolsResp.pools.find((p) => p.provider === provider);
  if (!pool) notFound();

  const { transactions, meta: txnMeta } = txnsResp;
  const forecasts = forecastsResp?.forecasts ?? [];
  const forecastMeta = forecastsResp?.meta ?? txnMeta;
  const forecast = forecasts.find((f) => f.pool_id === provider);

  return (
    <main className="min-h-dvh bg-background px-4 py-8 sm:py-12">
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-6">
        {/* Top bar */}
        <header className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-2">
            <Link
              href="/"
              className="text-brand text-label-md hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
            >
              ← Dashboard
            </Link>
          </div>
          <ThemeToggle />
        </header>

        <DataQualityBanner meta={txnMeta} />

        {/* Provider identity + balance card */}
        <section className="bg-surface border border-default rounded-xl shadow-card p-5 flex flex-col gap-4">
          <div className="flex items-center gap-3">
            <ProviderLogo provider={provider} size="lg" />
            <div>
              <p className="text-headline-sm text-primary">
                <ProviderLabel provider={provider} />
              </p>
              <p className="text-body-sm text-secondary">
                {agent.name} · {agent.area}
              </p>
            </div>
          </div>

          <div>
            <p className="text-label-md text-secondary">e-Money Balance</p>
            <p className="text-display-md tabular-nums-bv text-primary leading-none">
              ৳{fmt(pool.balance)}
            </p>
            <p className="text-body-sm text-tertiary mt-1">
              Separate pool · not interchangeable with other providers or
              physical cash
            </p>
          </div>

          <div className="flex items-center gap-3">
            <PoolStatusChip status={pool.status} />
          </div>
        </section>

        {/* Forecast & warnings — Phase 2 */}
        {forecast ? (
          <ForecastPanel forecast={forecast} meta={forecastMeta} />
        ) : (
          <section className="bg-surface-high border border-default rounded-lg px-4 py-5">
            <p className="text-label-md text-tertiary">Forecast unavailable</p>
            <p className="text-body-sm text-tertiary mt-1">
              No forecast data returned for this pool.
            </p>
          </section>
        )}

        {/* Recent transactions for this provider */}
        <section className="flex flex-col gap-2">
          <h2 className="text-title-sm text-secondary px-1">
            Recent Transactions
          </h2>
          <div className="bg-surface border border-default rounded-lg shadow-card overflow-hidden">
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
