import { getAgent, getAlerts, getPools, getForecast, getCases } from "@/lib/api";
import { LiveDashboard } from "@/components/live-dashboard";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const [agent, poolsResp, forecastsResp, alertsResp, casesResp] =
    await Promise.all([
      getAgent(),
      getPools(),
      getForecast().catch(() => null),
      getAlerts().catch(() => null),
      getCases().catch(() => null),
    ]);

  return (
    <LiveDashboard
      agent={agent}
      initialPoolsResp={poolsResp}
      initialForecastsResp={forecastsResp}
      initialAlertsResp={alertsResp}
      initialCasesResp={casesResp}
    />
  );
}
