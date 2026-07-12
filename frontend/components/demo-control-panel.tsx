"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  X,
  ChevronUp,
  Play,
  Pause,
  RotateCcw,
  Zap,
  AlertTriangle,
  Radio,
  CheckCircle2,
  XCircle,
  Terminal,
} from "lucide-react";
import type { Provider, AnomalyType } from "@/lib/types";
import {
  simStart,
  simPause,
  simReset,
  simEidRush,
  simInjectAnomaly,
  simBreakFeed,
  simRestoreFeed,
} from "@/lib/api";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface DemoLogEntry {
  id: number;
  time: string;
  message: string;
}

interface DemoControlPanelProps {
  simTime: string | null;
  tick: number;
  isConnected: boolean;
  isLive: boolean;
  demoLog: DemoLogEntry[];
  onLog: (message: string) => void;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const PROVIDERS: Provider[] = ["bkash", "nagad", "rocket"];
const PROVIDER_LABELS: Record<Provider, string> = {
  bkash: "bKash",
  nagad: "Nagad",
  rocket: "Rocket",
};
const ANOMALY_TYPES: AnomalyType[] = [
  "structuring",
  "velocity_spike",
  "off_hours_burst",
  "balance_inconsistency",
];
const ANOMALY_LABELS: Record<AnomalyType, string> = {
  structuring: "Structuring",
  velocity_spike: "Velocity Spike",
  off_hours_burst: "Off-Hours Burst",
  balance_inconsistency: "Balance Inconsistency",
};

// ─── Status dot ────────────────────────────────────────────────────────────────

function StatusDot({ isLive, isConnected }: { isLive: boolean; isConnected: boolean }) {
  if (isLive)
    return (
      <span className="flex items-center gap-1.5 text-label-sm" style={{ color: "var(--bv-success)" }}>
        <span className="size-1.5 rounded-full animate-pulse" style={{ backgroundColor: "var(--bv-success)" }} />
        LIVE
      </span>
    );
  if (isConnected)
    return (
      <span className="flex items-center gap-1.5 text-label-sm" style={{ color: "var(--bv-warning)" }}>
        <span className="size-1.5 rounded-full" style={{ backgroundColor: "var(--bv-warning)" }} />
        Connected
      </span>
    );
  return (
    <span className="flex items-center gap-1.5 text-label-sm text-tertiary">
      <span className="size-1.5 rounded-full bg-tertiary" />
      Disconnected
    </span>
  );
}

// ─── Scenario card ─────────────────────────────────────────────────────────────

function ScenarioCard({
  icon,
  title,
  description,
  children,
  accent = "var(--bv-warning)",
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
  children: React.ReactNode;
  accent?: string;
}) {
  return (
    <div
      className="rounded-xl overflow-hidden border"
      style={{
        borderColor: `color-mix(in srgb, ${accent} 25%, transparent)`,
        background: `color-mix(in srgb, ${accent} 5%, var(--bv-surface))`,
      }}
    >
      <div className="px-4 pt-4 pb-3">
        <div className="flex items-start gap-3 mb-3">
          <span
            className="flex items-center justify-center size-8 rounded-lg shrink-0"
            style={{ backgroundColor: `color-mix(in srgb, ${accent} 18%, transparent)`, color: accent }}
          >
            {icon}
          </span>
          <div>
            <p className="text-title-sm text-primary">{title}</p>
            <p className="text-body-sm text-tertiary">{description}</p>
          </div>
        </div>
        {children}
      </div>
    </div>
  );
}

// ─── Pill button ──────────────────────────────────────────────────────────────

function PillBtn({
  label,
  icon,
  onClick,
  loading,
  disabled,
  variant = "default",
}: {
  label: string;
  icon?: React.ReactNode;
  onClick: () => Promise<void>;
  loading?: boolean;
  disabled?: boolean;
  variant?: "default" | "danger" | "success" | "ghost";
}) {
  const styles: Record<string, { bg: string; text: string; border: string }> = {
    default: {
      bg: "var(--bv-surface-high)",
      text: "var(--bv-text-secondary)",
      border: "var(--bv-border)",
    },
    danger: {
      bg: "color-mix(in srgb, var(--bv-danger) 12%, transparent)",
      text: "var(--bv-danger)",
      border: "color-mix(in srgb, var(--bv-danger) 30%, transparent)",
    },
    success: {
      bg: "color-mix(in srgb, var(--bv-success) 12%, transparent)",
      text: "var(--bv-success)",
      border: "color-mix(in srgb, var(--bv-success) 30%, transparent)",
    },
    ghost: {
      bg: "transparent",
      text: "var(--bv-text-secondary)",
      border: "var(--bv-border)",
    },
  };
  const s = styles[variant];

  return (
    <button
      onClick={onClick}
      disabled={loading || disabled}
      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-label-md font-medium border transition-all duration-fast disabled:opacity-40 disabled:cursor-not-allowed hover:brightness-110 active:scale-95"
      style={{ background: s.bg, color: s.text, borderColor: s.border }}
    >
      {loading ? (
        <span className="size-3.5 rounded-full border-2 border-current border-t-transparent animate-spin" />
      ) : (
        icon
      )}
      {label}
    </button>
  );
}

// ─── Segmented select ─────────────────────────────────────────────────────────

function SegmentedSelect<T extends string>({
  value,
  onChange,
  options,
  labels,
}: {
  value: T;
  onChange: (v: T) => void;
  options: readonly T[];
  labels: Record<T, string>;
}) {
  return (
    <div
      className="flex items-center gap-0.5 p-0.5 rounded-lg"
      style={{ backgroundColor: "var(--bv-surface-high)" }}
    >
      {options.map((o) => (
        <button
          key={o}
          onClick={() => onChange(o)}
          className="px-2.5 py-1 rounded-md text-label-sm font-medium transition-all duration-fast"
          style={
            o === value
              ? {
                  background: "var(--bv-surface)",
                  color: "var(--bv-text-primary)",
                  boxShadow: "0 1px 3px var(--bv-shadow-card)",
                }
              : { color: "var(--bv-text-tertiary)" }
          }
        >
          {labels[o]}
        </button>
      ))}
    </div>
  );
}

// ─── Log entry ────────────────────────────────────────────────────────────────

function LogEntry({ entry, index }: { entry: DemoLogEntry; index: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.15, delay: index * 0.02 }}
      className="flex gap-3 py-1.5 border-b border-default last:border-b-0"
    >
      <span
        className="text-label-sm tabular-nums-bv shrink-0 mt-0.5"
        style={{ color: "var(--bv-text-tertiary)", fontFamily: "monospace" }}
      >
        {entry.time}
      </span>
      <span
        className="text-body-sm flex-1 min-w-0 break-words"
        style={{ color: "var(--bv-text-secondary)", fontFamily: "monospace" }}
      >
        {entry.message}
      </span>
    </motion.div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export function DemoControlPanel({
  simTime,
  tick,
  isConnected,
  isLive,
  demoLog,
  onLog,
}: DemoControlPanelProps) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastSuccess, setLastSuccess] = useState<string | null>(null);

  const [anomalyProvider, setAnomalyProvider] = useState<Provider>("bkash");
  const [anomalyType, setAnomalyType] = useState<AnomalyType>("structuring");
  const [feedProvider, setFeedProvider] = useState<Provider>("nagad");
  const [feedMode, setFeedMode] = useState<"stale" | "degraded">("stale");

  const simDisplay = simTime ? simTime.substring(11, 16) + " UTC" : "--:--";

  async function run(key: string, fn: () => Promise<{ applied: string }>) {
    setLoading(key);
    setError(null);
    setLastSuccess(null);
    try {
      const res = await fn();
      setLastSuccess(res.applied);
      onLog(res.applied);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setLoading(null);
    }
  }

  return (
    <>
      {/* Floating toggle button */}
      <motion.button
        onClick={() => setOpen((o) => !o)}
        whileHover={{ scale: 1.04 }}
        whileTap={{ scale: 0.96 }}
        className="fixed bottom-5 right-5 z-50 flex items-center gap-2 px-3.5 py-2.5 rounded-xl text-label-sm font-mono shadow-card"
        style={{
          background: "var(--bv-surface)",
          border: "1.5px dashed var(--bv-warning)",
          color: "var(--bv-warning)",
        }}
        aria-label={open ? "Close demo panel" : "Open demo panel"}
      >
        <Terminal className="size-3.5" />
        <span>DEMO</span>
        <StatusDot isLive={isLive} isConnected={isConnected} />
        <ChevronUp
          className={`size-3.5 transition-transform duration-300 ${open ? "rotate-180" : ""}`}
        />
      </motion.button>

      {/* Panel */}
      <AnimatePresence>
        {open && (
          <>
            <motion.div
              key="demo-backdrop"
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.4 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-40 bg-black"
              onClick={() => setOpen(false)}
            />

            <motion.div
              key="demo-panel"
              initial={{ y: "100%", opacity: 0.5 }}
              animate={{ y: 0, opacity: 1 }}
              exit={{ y: "100%", opacity: 0 }}
              transition={{ type: "spring", damping: 30, stiffness: 280 }}
              className="fixed inset-x-0 bottom-0 z-50 overflow-y-auto rounded-t-2xl"
              style={{
                maxHeight: "80vh",
                background: "var(--bv-surface)",
                borderTop: "2px solid var(--bv-warning)",
                boxShadow: "0 -8px 40px rgba(0,0,0,0.25)",
              }}
              data-lenis-prevent
            >
              {/* Handle bar */}
              <div className="flex justify-center pt-2 pb-0">
                <div
                  className="w-10 h-1 rounded-pill"
                  style={{ backgroundColor: "var(--bv-border)" }}
                />
              </div>

              {/* Header */}
              <div
                className="sticky top-0 z-10 px-5 py-3 flex items-center justify-between gap-3"
                style={{
                  background: "var(--bv-surface)",
                  borderBottom: "1px solid var(--bv-border)",
                  backdropFilter: "blur(12px)",
                }}
              >
                <div className="flex items-center gap-3 flex-wrap">
                  <span
                    className="px-2 py-0.5 rounded-md text-label-sm font-mono font-bold uppercase tracking-wider"
                    style={{
                      border: "1px solid var(--bv-warning)",
                      color: "var(--bv-warning)",
                      background: "color-mix(in srgb, var(--bv-warning) 8%, transparent)",
                    }}
                  >
                    Demo Control
                  </span>
                  <span
                    className="text-body-sm font-mono"
                    style={{ color: "var(--bv-text-tertiary)" }}
                  >
                    {simDisplay}
                    {isLive && ` · tick #${tick}`}
                  </span>
                  <StatusDot isLive={isLive} isConnected={isConnected} />
                </div>
                <button
                  onClick={() => setOpen(false)}
                  className="grid place-items-center size-8 rounded-pill transition-colors duration-fast"
                  style={{ background: "var(--bv-surface-high)", color: "var(--bv-text-secondary)" }}
                  aria-label="Close demo panel"
                >
                  <X className="size-4" />
                </button>
              </div>

              <div className="p-5 space-y-4 max-w-2xl mx-auto pb-8">
                {/* Disclaimer */}
                <p
                  className="text-body-sm font-mono rounded-lg px-3 py-2.5 border border-dashed"
                  style={{
                    color: "var(--bv-text-tertiary)",
                    borderColor: "var(--bv-border)",
                    background: "var(--bv-surface-high)",
                  }}
                >
                  Presenter tool · all controls generate synthetic events only · no real financial actions
                </p>

                {/* Error / success toast */}
                <AnimatePresence>
                  {error && (
                    <motion.div
                      initial={{ opacity: 0, y: -4 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0 }}
                      className="flex items-center gap-2 rounded-lg px-3 py-2.5"
                      style={{
                        background: "color-mix(in srgb, var(--bv-danger) 10%, transparent)",
                        border: "1px solid color-mix(in srgb, var(--bv-danger) 30%, transparent)",
                      }}
                    >
                      <XCircle className="size-4 shrink-0" style={{ color: "var(--bv-danger)" }} />
                      <p className="text-body-sm font-mono" style={{ color: "var(--bv-danger)" }}>
                        {error}
                      </p>
                    </motion.div>
                  )}
                  {lastSuccess && (
                    <motion.div
                      initial={{ opacity: 0, y: -4 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0 }}
                      className="flex items-center gap-2 rounded-lg px-3 py-2.5"
                      style={{
                        background: "color-mix(in srgb, var(--bv-success) 10%, transparent)",
                        border: "1px solid color-mix(in srgb, var(--bv-success) 30%, transparent)",
                      }}
                    >
                      <CheckCircle2 className="size-4 shrink-0" style={{ color: "var(--bv-success)" }} />
                      <p className="text-body-sm font-mono" style={{ color: "var(--bv-success)" }}>
                        {lastSuccess}
                      </p>
                    </motion.div>
                  )}
                </AnimatePresence>

                {/* Simulation controls */}
                <ScenarioCard
                  icon={<Play className="size-4" />}
                  title="Simulation Clock"
                  description="Control the synthetic event clock"
                  accent="var(--bv-success)"
                >
                  <div className="flex flex-wrap gap-2">
                    <PillBtn
                      label="Start"
                      icon={<Play className="size-3.5" />}
                      variant="success"
                      loading={loading === "start"}
                      onClick={() => run("start", () => simStart({ speed: 1 }))}
                    />
                    <PillBtn
                      label="Pause"
                      icon={<Pause className="size-3.5" />}
                      variant="ghost"
                      loading={loading === "pause"}
                      disabled={!isLive}
                      onClick={() => run("pause", simPause)}
                    />
                    <PillBtn
                      label="Reset"
                      icon={<RotateCcw className="size-3.5" />}
                      variant="danger"
                      loading={loading === "reset"}
                      onClick={() => run("reset", simReset)}
                    />
                  </div>
                </ScenarioCard>

                {/* Scenario A */}
                <ScenarioCard
                  icon={<Zap className="size-4" />}
                  title="Scenario A — Liquidity Pressure"
                  description="Simulate high-intensity cash-out pressure → triggers liquidity alert"
                  accent="var(--bv-danger)"
                >
                  <PillBtn
                    label="Trigger Eid Rush"
                    icon={<Zap className="size-3.5" />}
                    variant="danger"
                    loading={loading === "eid"}
                    onClick={() =>
                      run("eid", () =>
                        simEidRush({ provider: "physical_cash", intensity: "high" })
                      )
                    }
                  />
                </ScenarioCard>

                {/* Scenario B */}
                <ScenarioCard
                  icon={<AlertTriangle className="size-4" />}
                  title="Scenario B — Unusual Activity"
                  description="Inject an unusual transaction pattern on a selected provider"
                  accent="var(--bv-warning)"
                >
                  <div className="flex flex-col gap-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-label-sm text-secondary w-16 shrink-0">Provider</span>
                      <SegmentedSelect
                        value={anomalyProvider}
                        onChange={setAnomalyProvider}
                        options={PROVIDERS}
                        labels={PROVIDER_LABELS}
                      />
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-label-sm text-secondary w-16 shrink-0">Type</span>
                      <SegmentedSelect
                        value={anomalyType}
                        onChange={setAnomalyType}
                        options={ANOMALY_TYPES}
                        labels={ANOMALY_LABELS}
                      />
                    </div>
                    <PillBtn
                      label="Inject Anomaly"
                      icon={<AlertTriangle className="size-3.5" />}
                      variant="danger"
                      loading={loading === "anomaly"}
                      onClick={() =>
                        run("anomaly", () =>
                          simInjectAnomaly({ provider: anomalyProvider, type: anomalyType })
                        )
                      }
                    />
                  </div>
                </ScenarioCard>

                {/* Scenario C */}
                <ScenarioCard
                  icon={<Radio className="size-4" />}
                  title="Scenario C — Feed Quality"
                  description="Degrade or restore a provider's data feed"
                  accent="var(--bv-info)"
                >
                  <div className="flex flex-col gap-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-label-sm text-secondary w-16 shrink-0">Provider</span>
                      <SegmentedSelect
                        value={feedProvider}
                        onChange={setFeedProvider}
                        options={PROVIDERS}
                        labels={PROVIDER_LABELS}
                      />
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-label-sm text-secondary w-16 shrink-0">Mode</span>
                      <SegmentedSelect
                        value={feedMode}
                        onChange={(v) => setFeedMode(v as "stale" | "degraded")}
                        options={["stale", "degraded"] as const}
                        labels={{ stale: "Stale", degraded: "Degraded" }}
                      />
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <PillBtn
                        label="Break Feed"
                        icon={<XCircle className="size-3.5" />}
                        variant="danger"
                        loading={loading === "break"}
                        onClick={() =>
                          run("break", () =>
                            simBreakFeed({ provider: feedProvider, mode: feedMode })
                          )
                        }
                      />
                      <PillBtn
                        label="Restore"
                        icon={<CheckCircle2 className="size-3.5" />}
                        variant="success"
                        loading={loading === "restore"}
                        onClick={() =>
                          run("restore", () => simRestoreFeed({ provider: feedProvider }))
                        }
                      />
                    </div>
                  </div>
                </ScenarioCard>

                {/* Event log */}
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <Terminal className="size-3.5 text-tertiary" />
                    <p className="text-label-sm text-secondary uppercase tracking-wide">Event Log</p>
                    {demoLog.length > 0 && (
                      <span
                        className="px-1.5 py-0.5 rounded-sm text-label-sm tabular-nums-bv"
                        style={{
                          background: "var(--bv-surface-high)",
                          color: "var(--bv-text-tertiary)",
                        }}
                      >
                        {demoLog.length}
                      </span>
                    )}
                  </div>
                  {demoLog.length === 0 ? (
                    <div
                      className="rounded-lg px-4 py-4 text-center"
                      style={{ background: "var(--bv-surface-high)" }}
                    >
                      <p
                        className="text-body-sm font-mono"
                        style={{ color: "var(--bv-text-tertiary)" }}
                      >
                        No events yet — start the simulation
                      </p>
                    </div>
                  ) : (
                    <div
                      className="rounded-lg px-3 py-1 max-h-40 overflow-y-auto"
                      style={{ background: "var(--bv-surface-high)" }}
                    >
                      <AnimatePresence>
                        {demoLog.map((entry, i) => (
                          <LogEntry key={entry.id} entry={entry} index={i} />
                        ))}
                      </AnimatePresence>
                    </div>
                  )}
                </div>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
