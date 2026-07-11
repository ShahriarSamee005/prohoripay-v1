import { getAgent, getPools } from "@/lib/api";
import { ThemeToggle } from "@/components/theme-toggle";
import { HeroCard } from "@/components/hero-card";
import { PoolBreakdown } from "@/components/pool-breakdown";
import { ProviderCardRow } from "@/components/provider-card-row";
import { DataQualityBanner } from "@/components/data-quality-banner";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const [agent, poolsResp] = await Promise.all([getAgent(), getPools()]);
  const { pools, meta } = poolsResp;

  return (
    <main className="min-h-dvh bg-background px-4 py-8 sm:py-12">
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-6">
        {/* Top bar */}
        <header className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-headline-sm text-primary">ProhoriPay</h1>
            <p className="text-body-sm text-secondary">Advisory · synthetic data · humans decide</p>
          </div>
          <ThemeToggle />
        </header>

        {/* Data quality banner — hidden when ok, visible when degraded/stale */}
        <DataQualityBanner meta={meta} />

        {/* Hero — compliance-critical framing */}
        <HeroCard pools={pools} agentName={agent.name} agentArea={agent.area} />

        {/* Balance breakdown */}
        <PoolBreakdown pools={pools} />

        {/* Provider card row */}
        <ProviderCardRow pools={pools} />

        <footer className="text-body-sm text-tertiary text-center pb-4">
          Advisory only · no financial decisions are made automatically
        </footer>
      </div>
    </main>
  );
}
