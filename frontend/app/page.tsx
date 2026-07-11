import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { HealthStatus } from "@/components/health-status";
import { ThemeToggle } from "@/components/theme-toggle";

// Phase 0 placeholder. Proves the Blossom-Vermillion token port (magenta accent,
// surfaces, type scale) and the backend link. NOT the real dashboard.
export default function Home() {
  return (
    <main className="min-h-dvh bg-background px-4 py-10 sm:py-16">
      <div className="mx-auto flex w-full max-w-xl flex-col gap-6">
        <header className="flex items-start justify-between gap-4">
          <div className="flex flex-col gap-1">
            <h1 className="text-headline-lg text-primary">ProhoriPay</h1>
            <p className="text-body-md text-secondary">
              Advisory decision-support for multi-provider MFS super agents.
            </p>
          </div>
          <ThemeToggle />
        </header>

        {/* Magenta hero — the one accent, gradient + glow + on-brand text. */}
        <section className="bg-brand-gradient text-on-brand rounded-xl shadow-brand-glow p-6">
          <p className="text-label-md opacity-90">Blossom-Vermillion</p>
          <p className="text-display-sm tabular-nums-bv">Phase 0 scaffold</p>
          <p className="text-body-sm opacity-90">
            Design tokens ported · shadcn + Framer Motion + Lenis + Recharts
            wired.
          </p>
        </section>

        <Card>
          <CardHeader>
            <CardTitle>Backend connection</CardTitle>
            <CardDescription>
              Live probe of the FastAPI /health endpoint.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <HealthStatus />
          </CardContent>
        </Card>

        <footer className="text-body-sm text-tertiary">
          Advisory only · synthetic data · humans make every decision.
        </footer>
      </div>
    </main>
  );
}
