"use client";

import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronRight, Info, X } from "lucide-react";
import type {
  Alert,
  AlertContext,
  AlertSeverity,
  AnomalyType,
  Case,
  ExplainLang,
  Provider,
  ProviderFeedStatus,
} from "@/lib/types";
import { explain } from "@/lib/api";
import { CasePanel } from "./case-panel";
import {
  ExplanationBlock,
  getSessionLang,
  setSessionLang,
} from "./explanation-block";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fmtTime(ts: string): string {
  return ts.substring(11, 16) + " UTC";
}

function fmtVal(key: string, val: number | string): string {
  if (typeof val !== "number") return String(val);
  if (key === "txn_per_min") return `${val}/min`;
  if (key === "burn_rate_per_min") return `${val} BDT/min`;
  if (
    key.includes("balance") ||
    key === "amount_avg" ||
    key.includes("amount")
  ) {
    return `৳${val.toLocaleString()}`;
  }
  return String(val);
}

const KEY_LABELS: Record<string, string> = {
  txn_per_min: "Txn Rate",
  amount_avg: "Avg Amount",
  unique_accounts_per_20min: "Accounts / 20 min",
  balance_floor: "Balance Floor",
  balance_current: "Current Balance",
  burn_rate_per_min: "Burn Rate",
};

function humanKey(key: string): string {
  return (
    KEY_LABELS[key] ??
    key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
  );
}

function anomalyLabel(t: AnomalyType): string {
  const m: Record<AnomalyType, string> = {
    structuring: "Structuring",
    velocity_spike: "Velocity Spike",
    off_hours_burst: "Off-Hours Burst",
    balance_inconsistency: "Balance Inconsistency",
  };
  return m[t];
}

function poolLabel(a: Alert): string {
  if (a.provider === "bkash") return "bKash";
  if (a.provider === "nagad") return "Nagad";
  if (a.provider === "rocket") return "Rocket";
  return "Physical Cash";
}

function severityStyle(s: AlertSeverity) {
  if (s === "high")
    return {
      stripe: "var(--bv-danger)",
      textClass: "text-danger",
    };
  if (s === "medium")
    return {
      stripe: "var(--bv-warning)",
      textClass: "text-warning",
    };
  return {
    stripe: "var(--bv-info)",
    textClass: "text-info",
  };
}

function worstSeverity(alerts: Alert[]): AlertSeverity {
  if (alerts.some((a) => a.severity === "high")) return "high";
  if (alerts.some((a) => a.severity === "medium")) return "medium";
  return "low";
}

// Phase-3 static Bangla templates — still used as initialFallback for Phase 6
// ExplanationBlock (shown while Groq responds, and if the request fails entirely).
const STATIC_BANGLA: Record<string, string> = {
  alert_0001: "⚠️ bKash-এ অস্বাভাবিক লেনদেন ধরন — রিভিউ প্রয়োজন।",
  alert_0002: "⚠️ Nagad-এ লেনদেনের হার অস্বাভাবিক — পর্যালোচনা করুন।",
  alert_0003: "⚠️ ক্যাশ ড্রয়ারে অর্থ কম — দ্রুত ব্যবস্থা নিন।",
  alert_0004: "⚠️ Rocket-এ রাতের অস্বাভাবিক লেনদেন — পর্যালোচনা সম্পন্ন।",
};

// ── Compact explanation line for the alert card ───────────────────────────────
// Calls /api/explain and shows the text inline with a source badge. Falls back
// to the static Bangla template so the card is never blank.

function CompactExplain({
  alertId,
  lang,
  fallback,
}: {
  alertId: string;
  lang: ExplainLang;
  fallback?: string;
}) {
  const [text, setText] = useState<string>(fallback ?? "");
  const [source, setSource] = useState<"groq" | "fallback" | null>(null);
  const [loading, setLoading] = useState(true);
  const reqRef = useRef(0);

  useEffect(() => {
    const reqId = ++reqRef.current;
    setLoading(true);
    setText(fallback ?? "");
    setSource(null);
    explain({ kind: "alert", id: alertId, lang })
      .then((r) => {
        if (reqRef.current !== reqId) return;
        setText(r.text);
        setSource(r.source);
      })
      .catch(() => {
        if (reqRef.current !== reqId) return;
        setText(fallback ?? (lang === "bn"
          ? "ব্যাখ্যা পাওয়া যায়নি। মানব পর্যালোচনা প্রয়োজন।"
          : "Explanation unavailable. Human review recommended."));
        setSource("fallback");
      })
      .finally(() => {
        if (reqRef.current === reqId) setLoading(false);
      });
  }, [alertId, lang, fallback]);

  return (
    <motion.div
      initial={{ opacity: 0, height: 0, marginTop: 0 }}
      animate={{ opacity: 1, height: "auto", marginTop: 8 }}
      exit={{ opacity: 0, height: 0, marginTop: 0 }}
      className="overflow-hidden"
    >
      {loading ? (
        <div className="space-y-1.5 animate-pulse">
          <div className="h-3 rounded-sm w-full" style={{ backgroundColor: "var(--bv-surface-high)" }} />
          <div className="h-3 rounded-sm w-4/5" style={{ backgroundColor: "var(--bv-surface-high)" }} />
        </div>
      ) : (
        <div className="space-y-1">
          <p className="text-body-sm text-primary leading-relaxed">{text}</p>
          {source && (
            <span
              className="inline-flex items-center px-1.5 py-0.5 rounded-sm text-label-sm"
              style={{
                backgroundColor:
                  source === "groq"
                    ? "color-mix(in srgb, var(--bv-brand) 12%, transparent)"
                    : "color-mix(in srgb, var(--bv-text-secondary) 12%, transparent)",
                color:
                  source === "groq"
                    ? "var(--bv-brand)"
                    : "var(--bv-text-secondary)",
              }}
            >
              {source === "groq" ? "AI" : "Auto"}
            </span>
          )}
        </div>
      )}
    </motion.div>
  );
}

// ─── Baseline vs Observed comparison ─────────────────────────────────────────

function ComparisonRows({
  baseline,
  observed,
}: {
  baseline: Record<string, number | string>;
  observed: Record<string, number | string>;
}) {
  const allKeys = Array.from(
    new Set([...Object.keys(baseline), ...Object.keys(observed)])
  );
  return (
    <div className="space-y-1.5">
      {allKeys.map((key) => {
        const bVal = baseline[key];
        const oVal = observed[key];
        const hasBase = bVal !== undefined;
        const hasObs = oVal !== undefined;

        if (hasBase && hasObs) {
          return (
            <div key={key} className="flex items-center gap-2 flex-wrap text-body-sm">
              <span className="text-secondary shrink-0">{humanKey(key)}</span>
              <span className="text-tertiary tabular-nums-bv">{fmtVal(key, bVal)}</span>
              <span className="text-tertiary">→</span>
              <span className="text-primary font-semibold tabular-nums-bv">
                {fmtVal(key, oVal)}
              </span>
            </div>
          );
        }
        if (hasBase) {
          return (
            <div key={key} className="flex items-center gap-2 flex-wrap text-body-sm">
              <span className="text-secondary shrink-0">Baseline {humanKey(key)}</span>
              <span className="text-tertiary tabular-nums-bv">{fmtVal(key, bVal)}</span>
            </div>
          );
        }
        return (
          <div key={key} className="flex items-center gap-2 flex-wrap text-body-sm">
            <span className="text-secondary shrink-0">Observed {humanKey(key)}</span>
            <span className="text-primary font-semibold tabular-nums-bv">
              {fmtVal(key, oVal!)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ─── Confidence factor bar ────────────────────────────────────────────────────

function FactorBar({ label, value }: { label: string; value: number }) {
  const pct = Math.round(value * 100);
  const barColor =
    pct >= 75
      ? "var(--bv-success)"
      : pct >= 50
        ? "var(--bv-warning)"
        : "var(--bv-danger)";
  return (
    <div className="space-y-0.5">
      <div className="flex items-center justify-between gap-2">
        <span className="text-body-sm text-secondary">{label}</span>
        <span className="text-label-sm tabular-nums-bv text-secondary">{pct}%</span>
      </div>
      <div className="h-1 rounded-pill bg-surface-high overflow-hidden">
        <div
          className="h-full rounded-pill"
          style={{ width: `${pct}%`, backgroundColor: barColor }}
        />
      </div>
    </div>
  );
}

// ─── Eid context chip ─────────────────────────────────────────────────────────

function EidContextChip({ context }: { context: AlertContext }) {
  if (!context.active_event) return null;
  return (
    <div className="flex items-start gap-2.5 rounded-lg border border-default bg-surface-high px-3.5 py-2.5">
      <Info className="size-4 text-info mt-0.5 shrink-0" />
      <p className="text-body-sm text-primary">{context.note}</p>
    </div>
  );
}

// ─── Active cases strip ───────────────────────────────────────────────────────

const CASE_STATUS_COLOR: Record<string, string> = {
  routed: "var(--bv-warning)",
  acknowledged: "var(--bv-brand)",
  escalated: "var(--bv-danger)",
};

const CASE_OWNER_LABELS: Record<string, string> = {
  field_officer: "Field Officer",
  risk_reviewer: "Risk Reviewer",
  supervisor: "Supervisor",
  area_manager: "Area Manager",
};

function ActiveCasesStrip({
  cases,
  alerts,
  onOpenAlert,
}: {
  cases: Case[];
  alerts: Alert[];
  onOpenAlert: (alert: Alert) => void;
}) {
  const active = (cases ?? []).filter((c) => c.status !== "resolved");
  if (active.length === 0) return null;

  return (
    <div className="bg-surface border border-default rounded-lg overflow-hidden">
      <div className="px-4 py-2.5 border-b border-default flex items-center justify-between gap-3">
        <p className="text-label-sm text-secondary uppercase tracking-wide">
          Active Cases
        </p>
        <span
          className="px-2 py-0.5 rounded-pill text-label-sm text-on-brand tabular-nums-bv"
          style={{ backgroundColor: "var(--bv-warning)" }}
        >
          {active.length}
        </span>
      </div>
      <div className="divide-y divide-default">
        {active.map((c) => {
          const linkedAlert = alerts.find((a) => a.id === c.alert_id);
          return (
            <button
              key={c.id}
              onClick={() => linkedAlert && onOpenAlert(linkedAlert)}
              className="w-full flex items-center justify-between gap-3 px-4 py-3 hover:bg-surface-high transition-colors text-left"
            >
              <div className="flex items-center gap-2.5 min-w-0">
                <div
                  className="size-2 rounded-pill shrink-0"
                  style={{
                    backgroundColor:
                      CASE_STATUS_COLOR[c.status] ?? "var(--bv-text-tertiary)",
                  }}
                />
                <div className="min-w-0">
                  <p className="text-title-sm text-primary truncate">
                    {CASE_OWNER_LABELS[c.owner_role] ?? c.owner_role}
                  </p>
                  <p className="text-body-sm text-tertiary">
                    {c.provider ?? "Physical Cash"} · {c.id}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span
                  className="px-2 py-0.5 rounded-pill text-label-sm"
                  style={{
                    backgroundColor:
                      CASE_STATUS_COLOR[c.status] ?? "var(--bv-surface-high)",
                    color:
                      c.status in CASE_STATUS_COLOR ? "#fff" : "var(--bv-text-secondary)",
                  }}
                >
                  {c.status}
                </span>
                <ChevronRight className="size-3.5 text-tertiary" />
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ─── Alert card ───────────────────────────────────────────────────────────────

const LANG_OPTS: { value: ExplainLang; label: string }[] = [
  { value: "en", label: "EN" },
  { value: "bn", label: "বাংলা" },
  { value: "banglish", label: "Banglish" },
];

function AlertCard({
  alert,
  hasCase,
  onOpen,
  feedStatus,
}: {
  alert: Alert;
  hasCase: boolean;
  onOpen: () => void;
  feedStatus?: ProviderFeedStatus;
}) {
  // Initialise from session storage; hydrated on first client render.
  const [lang, setLangState] = useState<ExplainLang>("en");
  useEffect(() => { setLangState(getSessionLang()); }, []);

  function handleLang(l: ExplainLang) {
    setLangState(l);
    setSessionLang(l);
  }

  const sv = severityStyle(alert.severity);
  const rawConf = Math.round(alert.confidence * 100);
  const adjConf = feedStatus
    ? Math.round(alert.confidence * feedStatus.confidence_modifier * 100)
    : rawConf;
  const confDegraded = feedStatus && adjConf < rawConf;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-surface border border-default rounded-lg shadow-card overflow-hidden"
    >
      {/* Severity stripe */}
      <div className="h-1" style={{ backgroundColor: sv.stripe }} />

      <div className="p-4 space-y-3">
        {/* Row 1: badges + time */}
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="px-2 py-0.5 rounded-sm bg-surface-high text-label-sm text-secondary uppercase tracking-wide">
              {alert.type}
            </span>
            <span
              className="px-2 py-0.5 rounded-sm text-label-sm text-on-brand capitalize"
              style={{ backgroundColor: sv.stripe }}
            >
              {alert.severity}
            </span>
            {alert.anomaly_type && (
              <span className="px-2 py-0.5 rounded-sm bg-surface-high text-label-sm text-secondary">
                {anomalyLabel(alert.anomaly_type)}
              </span>
            )}
            {hasCase && (
              <span className="px-2 py-0.5 rounded-sm bg-brand text-on-brand text-label-sm">
                Case
              </span>
            )}
          </div>
          <span className="text-body-sm text-tertiary shrink-0 tabular-nums-bv">
            {fmtTime(alert.ts)}
          </span>
        </div>

        {/* Row 2: label + confidence */}
        <div className="flex items-start justify-between gap-3">
          <p className={`text-title-sm ${sv.textClass}`}>{alert.label}</p>
          <span className="text-label-sm text-secondary shrink-0 tabular-nums-bv">
            {confDegraded ? (
              <>
                <span className="text-warning">⚠ ~{adjConf}%</span>
                {" "}
                <span className="line-through opacity-50">{rawConf}%</span>
                {" conf."}
              </>
            ) : (
              <>{rawConf}% conf.</>
            )}
          </span>
        </div>

        {/* Provider / pool */}
        <p className="text-body-sm text-tertiary">{poolLabel(alert)}</p>

        {/* Evidence (evidence-first — authoritative, unchanged) */}
        <div>
          <p className="text-label-sm text-secondary mb-1.5">Evidence</p>
          <ul className="space-y-1">
            {alert.evidence.map((e, i) => (
              <li key={i} className="flex gap-2 text-body-sm text-primary">
                <span className="text-tertiary shrink-0">•</span>
                <span>{e}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Baseline vs Observed */}
        <div>
          <p className="text-label-sm text-secondary mb-1.5">Baseline vs Observed</p>
          <ComparisonRows baseline={alert.baseline} observed={alert.observed} />
        </div>

        {/* Bottom row: lang toggle (3 options) + view details */}
        <div className="flex items-center justify-between gap-2 pt-1 border-t border-default">
          <div className="flex items-center gap-1">
            {LANG_OPTS.map(({ value, label }) => (
              <button
                key={value}
                onClick={() => handleLang(value)}
                aria-pressed={lang === value}
                className={`px-2.5 py-1 rounded-pill text-label-sm transition-colors duration-fast ${
                  lang === value
                    ? "bg-brand text-on-brand"
                    : "bg-surface-high text-secondary hover:text-primary"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          <button
            onClick={onOpen}
            className="flex items-center gap-1 text-label-sm text-brand hover:text-brand-deep transition-colors"
          >
            View details
            <ChevronRight className="size-3.5" />
          </button>
        </div>

        {/* Compact explanation — powered by /api/explain (Phase 6).
            Falls back to static STATIC_BANGLA template; never goes blank. */}
        <AnimatePresence>
          {lang !== "en" && (
            <CompactExplain
              key={`${alert.id}-${lang}`}
              alertId={alert.id}
              lang={lang}
              fallback={lang === "bn" ? STATIC_BANGLA[alert.id] : undefined}
            />
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}

// ─── Detail drawer ────────────────────────────────────────────────────────────

function AlertDetailDrawer({
  alert,
  case_,
  onClose,
  onCaseUpdate,
  feedStatus,
}: {
  alert: Alert | null;
  case_: Case | null;
  onClose: () => void;
  onCaseUpdate: (updated: Case) => void;
  feedStatus?: ProviderFeedStatus;
}) {
  return (
    <AnimatePresence>
      {alert && (
        <>
          {/* Backdrop */}
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-40"
            style={{ backgroundColor: "rgba(30, 20, 24, 0.45)" }}
            onClick={onClose}
          />

          {/* Drawer panel */}
          <motion.div
            key="drawer"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 30, stiffness: 280 }}
            className="fixed right-0 top-0 h-full w-full max-w-md bg-surface border-l border-default z-50 overflow-y-auto"
            data-lenis-prevent
          >
            {/* Sticky header */}
            <div className="sticky top-0 bg-surface border-b border-default px-4 py-3 flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="px-2 py-0.5 rounded-sm bg-surface-high text-label-sm text-secondary uppercase tracking-wide">
                  {alert.type}
                </span>
                <span
                  className="px-2 py-0.5 rounded-sm text-label-sm text-on-brand capitalize"
                  style={{
                    backgroundColor: severityStyle(alert.severity).stripe,
                  }}
                >
                  {alert.severity}
                </span>
                {alert.anomaly_type && (
                  <span className="px-2 py-0.5 rounded-sm bg-surface-high text-label-sm text-secondary">
                    {anomalyLabel(alert.anomaly_type)}
                  </span>
                )}
              </div>
              <button
                onClick={onClose}
                className="grid place-items-center size-8 rounded-pill bg-surface-high text-secondary hover:text-primary transition-colors shrink-0"
                aria-label="Close detail panel"
              >
                <X className="size-4" />
              </button>
            </div>

            <div className="p-4 space-y-5">
              {/* Identity */}
              <div>
                <p className={`text-title-md ${severityStyle(alert.severity).textClass}`}>
                  {alert.label}
                </p>
                <p className="text-body-sm text-secondary mt-0.5">
                  {alert.anomaly_type
                    ? `${anomalyLabel(alert.anomaly_type)} · `
                    : ""}
                  {poolLabel(alert)} · {fmtTime(alert.ts)}
                </p>
              </div>

              {/* Phase 6 — Explanation block (sits alongside evidence, never replaces it) */}
              <ExplanationBlock
                kind="alert"
                id={alert.id}
                initialFallback={STATIC_BANGLA[alert.id]}
              />

              {/* Confidence */}
              <div className="bg-surface-high rounded-lg p-3 space-y-3">
                <div className="flex items-center justify-between">
                  <p className="text-label-sm text-secondary">Confidence</p>
                  <span className="text-title-sm tabular-nums-bv">
                    {feedStatus ? (
                      <>
                        <span className="text-warning">
                          ⚠ ~{Math.round(alert.confidence * feedStatus.confidence_modifier * 100)}%
                        </span>
                        {" "}
                        <span className="text-tertiary line-through text-label-sm">
                          {Math.round(alert.confidence * 100)}%
                        </span>
                      </>
                    ) : (
                      <>{Math.round(alert.confidence * 100)}%</>
                    )}
                  </span>
                </div>
                {alert.confidence_factors && (
                  <>
                    <FactorBar
                      label="Signal Stability"
                      value={1 - alert.confidence_factors.volatility}
                    />
                    <FactorBar
                      label="Sample Size"
                      value={alert.confidence_factors.sample_size}
                    />
                    <FactorBar
                      label="Data Freshness"
                      value={alert.confidence_factors.data_freshness}
                    />
                  </>
                )}
              </div>

              {/* Full evidence */}
              <div>
                <p className="text-label-sm text-secondary mb-2">Evidence</p>
                <ul className="space-y-1.5">
                  {alert.evidence.map((e, i) => (
                    <li key={i} className="flex gap-2 text-body-sm text-primary">
                      <span className="text-tertiary shrink-0">•</span>
                      <span>{e}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Baseline vs Observed */}
              <div>
                <p className="text-label-sm text-secondary mb-2">Baseline vs Observed</p>
                <div className="bg-surface-high rounded-lg p-3">
                  <ComparisonRows
                    baseline={alert.baseline}
                    observed={alert.observed}
                  />
                </div>
              </div>

              {/* Recommended context */}
              {alert.recommended_context && (
                <div>
                  <p className="text-label-sm text-secondary mb-2">
                    Recommended Context
                  </p>
                  <p className="text-body-sm text-primary bg-surface-high rounded-lg p-3">
                    {alert.recommended_context}
                  </p>
                </div>
              )}

              {/* Phase 4 coordination panel */}
              <CasePanel case_={case_} onUpdate={onCaseUpdate} />

              <p className="text-body-sm text-tertiary text-center pb-2">
                Advisory only · no action is taken automatically · a human decides
              </p>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

// ─── Main export ──────────────────────────────────────────────────────────────

export function AlertFeed({
  alerts,
  context,
  cases,
  onCaseUpdate,
  feedStatuses = {},
}: {
  alerts: Alert[];
  context: AlertContext | null;
  cases: Case[];
  onCaseUpdate: (updated: Case) => void;
  feedStatuses?: Partial<Record<Provider, ProviderFeedStatus>>;
}) {
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);

  const sv = worstSeverity(alerts);

  // The case linked to the currently open alert drawer
  const selectedCase =
    selectedAlert?.case_id
      ? (cases.find((c) => c.id === selectedAlert.case_id) ?? null)
      : null;

  function handleOpenAlert(alert: Alert) {
    setSelectedAlert(alert);
  }

  return (
    <>
      <section className="space-y-4" aria-label="Activity Alerts">
        {/* Section header */}
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-headline-sm text-primary">Activity Alerts</h2>
            <p className="text-body-sm text-secondary">
              Unusual patterns · liquidity pressure · requires review
            </p>
          </div>
          {alerts.length > 0 && (
            <span
              className="px-2.5 py-1 rounded-pill text-label-sm text-on-brand tabular-nums-bv shrink-0"
              style={{ backgroundColor: severityStyle(sv).stripe }}
            >
              {alerts.length}
            </span>
          )}
        </div>

        {/* Active cases strip — resolved cases are excluded */}
        <ActiveCasesStrip
          cases={cases}
          alerts={alerts}
          onOpenAlert={handleOpenAlert}
        />

        {/* Eid context chip — calm informational chip, different from alert cards */}
        {context?.active_event && <EidContextChip context={context} />}

        {/* Alert cards */}
        {alerts.length === 0 ? (
          <div className="bg-surface border border-default rounded-lg p-6 text-center">
            <p className="text-body-md text-tertiary">No active alerts</p>
          </div>
        ) : (
          <div className="space-y-3">
            {alerts.map((alert) => (
              <AlertCard
                key={alert.id}
                alert={alert}
                hasCase={!!alert.case_id}
                onOpen={() => handleOpenAlert(alert)}
                feedStatus={alert.provider ? feedStatuses[alert.provider] : undefined}
              />
            ))}
          </div>
        )}
      </section>

      {/* Detail drawer — layered above everything */}
      <AlertDetailDrawer
        alert={selectedAlert}
        case_={selectedCase}
        onClose={() => setSelectedAlert(null)}
        onCaseUpdate={onCaseUpdate}
        feedStatus={
          selectedAlert?.provider
            ? feedStatuses[selectedAlert.provider]
            : undefined
        }
      />
    </>
  );
}
