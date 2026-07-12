"use client";

import { useEffect, useReducer, useRef, useCallback } from "react";
import type {
  Agent,
  Pool,
  Meta,
  Forecast,
  Alert,
  AlertContext,
  Case,
  Provider,
  ProviderFeedStatus,
  PoolsResponse,
  ForecastsResponse,
  AlertsResponse,
  CasesResponse,
  BalanceUpdateEvent,
  ForecastUpdateEvent,
  AlertNewEvent,
  CaseUpdateEvent,
  FeedStatusEvent,
} from "@/lib/types";
import { subscribeToStream } from "@/lib/stream";
import { getPools, getForecast, getAlerts, getCases } from "@/lib/api";
import { motion } from "framer-motion";
import { ThemeToggle } from "@/components/theme-toggle";
import { HeroCard } from "@/components/hero-card";
import { ProviderBalanceStrip } from "@/components/provider-balance-strip";
import { ProviderCardRow } from "@/components/provider-card-row";
import { DataQualityBanner } from "@/components/data-quality-banner";
import { AlertFeed } from "@/components/alert-feed";
import { DemoControlPanel } from "@/components/demo-control-panel";
import type { DemoLogEntry } from "@/components/demo-control-panel";

// ─── State + reducer ──────────────────────────────────────────────────────────

interface DashState {
  pools: Pool[];
  poolsMeta: Meta;
  forecasts: Forecast[];
  forecastsMeta: Meta;
  alerts: Alert[];
  alertContext: AlertContext | null;
  cases: Case[];
  simTime: string | null;
  tick: number;
  isLive: boolean;
  isConnected: boolean;
  feedStatuses: Partial<Record<Provider, ProviderFeedStatus>>;
  demoLog: DemoLogEntry[];
  logCounter: number;
}

type DashAction =
  | { type: "SET_CONNECTED"; connected: boolean }
  | { type: "TICK"; simTime: string; tick: number }
  | { type: "BALANCE_UPDATE"; ev: BalanceUpdateEvent }
  | { type: "FORECAST_UPDATE"; ev: ForecastUpdateEvent }
  | { type: "ALERT_NEW"; ev: AlertNewEvent }
  | { type: "CASE_UPDATE"; ev: CaseUpdateEvent }
  | { type: "FEED_STATUS"; ev: FeedStatusEvent }
  | { type: "CASE_MUTATED"; updated: Case }
  | { type: "DEMO_LOG"; message: string }
  | { type: "CASH_PATCHED"; balance: number }
  | {
      type: "HYDRATE";
      poolsResp: PoolsResponse;
      forecastsResp: ForecastsResponse | null;
      alertsResp: AlertsResponse | null;
      casesResp: CasesResponse | null;
    };

function reducer(state: DashState, action: DashAction): DashState {
  switch (action.type) {
    case "SET_CONNECTED":
      return { ...state, isConnected: action.connected };

    case "TICK":
      return { ...state, simTime: action.simTime, tick: action.tick, isLive: true };

    case "BALANCE_UPDATE":
      return { ...state, pools: action.ev.pools, poolsMeta: action.ev.meta };

    case "CASH_PATCHED":
      return {
        ...state,
        pools: state.pools.map((p) =>
          p.kind === "physical_cash" ? { ...p, balance: action.balance } : p
        ),
      };

    case "FORECAST_UPDATE":
      return {
        ...state,
        forecasts: action.ev.forecasts,
        forecastsMeta: action.ev.meta,
      };

    case "ALERT_NEW": {
      const alert = action.ev.alert;
      if (state.alerts.some((a) => a.id === alert.id)) return state;
      return { ...state, alerts: [alert, ...state.alerts] };
    }

    case "CASE_UPDATE": {
      const c = action.ev.case;
      const exists = state.cases.some((x) => x.id === c.id);
      return {
        ...state,
        cases: exists
          ? state.cases.map((x) => (x.id === c.id ? c : x))
          : [...state.cases, c],
        // Wire up alert.case_id when a case is first created
        alerts: state.alerts.map((a) =>
          a.id === c.alert_id && !a.case_id ? { ...a, case_id: c.id } : a
        ),
      };
    }

    case "FEED_STATUS": {
      const { provider, data_quality, confidence_modifier } = action.ev;
      const updated = { ...state.feedStatuses };
      if (data_quality === "ok") {
        delete updated[provider];
      } else {
        updated[provider] = { data_quality, confidence_modifier };
      }
      return { ...state, feedStatuses: updated };
    }

    case "CASE_MUTATED":
      return {
        ...state,
        cases: state.cases.map((c) =>
          c.id === action.updated.id ? action.updated : c
        ),
      };

    case "DEMO_LOG": {
      const entry: DemoLogEntry = {
        id: state.logCounter + 1,
        time: state.simTime
          ? state.simTime.substring(11, 16) + " sim"
          : "--:--",
        message: action.message,
      };
      return {
        ...state,
        logCounter: state.logCounter + 1,
        demoLog: [entry, ...state.demoLog].slice(0, 20),
      };
    }

    case "HYDRATE":
      return {
        ...state,
        pools: action.poolsResp.pools,
        poolsMeta: action.poolsResp.meta,
        ...(action.forecastsResp && {
          forecasts: action.forecastsResp.forecasts,
          forecastsMeta: action.forecastsResp.meta,
        }),
        ...(action.alertsResp && {
          alerts: action.alertsResp.alerts,
          alertContext: action.alertsResp.context,
        }),
        ...(action.casesResp && {
          cases: action.casesResp.cases,
        }),
      };

    default:
      return state;
  }
}

// ─── LIVE chip ─────────────────────────────────────────────────────────────────

function LiveChip({ simTime }: { simTime: string | null }) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      className="flex items-center gap-1.5 px-2 py-0.5 rounded-pill bg-surface-high border border-default"
    >
      <span
        className="size-1.5 rounded-full animate-pulse"
        style={{ backgroundColor: "var(--bv-success)" }}
      />
      <span className="text-label-sm text-success">LIVE</span>
      {simTime && (
        <span className="text-body-sm text-tertiary tabular-nums-bv">
          {simTime.substring(11, 16)}
        </span>
      )}
    </motion.div>
  );
}

// ─── Props ────────────────────────────────────────────────────────────────────

interface LiveDashboardProps {
  agent: Agent;
  initialPoolsResp: PoolsResponse;
  initialForecastsResp: ForecastsResponse | null;
  initialAlertsResp: AlertsResponse | null;
  initialCasesResp: CasesResponse | null;
}

// ─── Main component ───────────────────────────────────────────────────────────

export function LiveDashboard({
  agent,
  initialPoolsResp,
  initialForecastsResp,
  initialAlertsResp,
  initialCasesResp,
}: LiveDashboardProps) {
  const [state, dispatch] = useReducer(reducer, {
    pools: initialPoolsResp.pools,
    poolsMeta: initialPoolsResp.meta,
    forecasts: initialForecastsResp?.forecasts ?? [],
    forecastsMeta: initialForecastsResp?.meta ?? initialPoolsResp.meta,
    alerts: initialAlertsResp?.alerts ?? [],
    alertContext: initialAlertsResp?.context ?? null,
    cases: initialCasesResp?.cases ?? [],
    simTime: null,
    tick: 0,
    isLive: false,
    isConnected: false,
    feedStatuses: {},
    demoLog: [],
    logCounter: 0,
  });

  // Track reconnects so we only re-hydrate on reconnect, not first connect
  const connectCount = useRef(0);

  const hydrateFromREST = useCallback(async () => {
    try {
      const [poolsResp, forecastsResp, alertsResp, casesResp] =
        await Promise.all([
          getPools(),
          getForecast().catch(() => null),
          getAlerts().catch(() => null),
          getCases().catch(() => null),
        ]);
      dispatch({ type: "HYDRATE", poolsResp, forecastsResp, alertsResp, casesResp });
    } catch {
      // Silent — SSE stream will push fresh data
    }
  }, []);

  useEffect(() => {
    const unsub = subscribeToStream({
      onTick: (ev) =>
        dispatch({ type: "TICK", simTime: ev.sim_time, tick: ev.tick }),

      onBalanceUpdate: (ev) => dispatch({ type: "BALANCE_UPDATE", ev }),

      onForecastUpdate: (ev) => dispatch({ type: "FORECAST_UPDATE", ev }),

      onAlertNew: (ev) => {
        dispatch({ type: "ALERT_NEW", ev });
        dispatch({
          type: "DEMO_LOG",
          message: `alert raised: ${ev.alert.label} (${ev.alert.pool_id})`,
        });
      },

      onCaseUpdate: (ev) => {
        dispatch({ type: "CASE_UPDATE", ev });
        dispatch({
          type: "DEMO_LOG",
          message: `case ${ev.case.id} → ${ev.case.status}`,
        });
      },

      onFeedStatus: (ev) => {
        dispatch({ type: "FEED_STATUS", ev });
        dispatch({
          type: "DEMO_LOG",
          message:
            ev.data_quality === "ok"
              ? `${ev.provider} feed restored`
              : `${ev.provider} feed ${ev.data_quality} — confidence ×${ev.confidence_modifier.toFixed(2)}`,
        });
      },

      onConnected: () => {
        dispatch({ type: "SET_CONNECTED", connected: true });
        if (connectCount.current > 0) {
          // Reconnect — fill the gap with REST snapshots
          hydrateFromREST();
        }
        connectCount.current++;
      },

      onDisconnected: () => dispatch({ type: "SET_CONNECTED", connected: false }),
    });

    return unsub;
  }, [hydrateFromREST]);

  function handleCaseUpdate(updated: Case) {
    dispatch({ type: "CASE_MUTATED", updated });
  }

  function handleDemoLog(message: string) {
    dispatch({ type: "DEMO_LOG", message });
  }

  function handleCashPatched(newBalance: number) {
    dispatch({ type: "CASH_PATCHED", balance: newBalance });
  }

  return (
    <main className="min-h-dvh bg-background px-4 py-8 sm:py-12">
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-6">
        {/* Top bar */}
        <header className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-headline-sm text-primary">ProhoriPay</h1>
              {state.isLive && <LiveChip simTime={state.simTime} />}
            </div>
            <p className="text-body-sm text-secondary">
              Advisory · synthetic data · humans decide
            </p>
          </div>
          <ThemeToggle />
        </header>

        {/* Data quality: global meta + per-provider live feed statuses */}
        <DataQualityBanner
          meta={state.poolsMeta.data_quality !== "ok" ? state.poolsMeta : null}
          feedStatuses={state.feedStatuses}
        />

        {/* Hero — physical cash drawer */}
        <HeroCard
          pools={state.pools}
          forecasts={state.forecasts}
          agentName={agent.name}
          agentArea={agent.area}
          onBalancePatched={handleCashPatched}
        />

        {/* e-Money balances — separate from the cash drawer */}
        <ProviderBalanceStrip pools={state.pools} />

        {/* Provider cards — visual entry points to detail pages */}
        <ProviderCardRow pools={state.pools} />

        {/* Alert feed with live cases */}
        <AlertFeed
          alerts={state.alerts}
          context={state.alertContext}
          cases={state.cases}
          onCaseUpdate={handleCaseUpdate}
          feedStatuses={state.feedStatuses}
        />

        <footer className="text-body-sm text-tertiary text-center pb-4">
          Advisory only · no financial decisions are made automatically
        </footer>
      </div>

      {/* Floating demo control panel — presenter tool */}
      <DemoControlPanel
        simTime={state.simTime}
        tick={state.tick}
        isConnected={state.isConnected}
        isLive={state.isLive}
        demoLog={state.demoLog}
        onLog={handleDemoLog}
      />
    </main>
  );
}
