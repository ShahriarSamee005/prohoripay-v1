// Types mirror shared/contract.md. Money is integer BDT; direction lives in deltas.
// These are the Phase 0/1 "final" shapes. Phase 2+ shapes are forward-declared
// there and will be added in their own phase — do not invent divergent shapes.

export type PoolId = "physical_cash" | "bkash" | "nagad" | "rocket";
/** e-money rails only (physical cash is shared, not a provider) */
export type Provider = "bkash" | "nagad" | "rocket";
export type TxnType = "cash_in" | "cash_out";
export type TxnStatus = "completed" | "pending" | "failed";
export type PoolStatus = "healthy" | "watch" | "critical";
export type PoolKind = "physical_cash" | "provider_emoney";

/** GET /health */
export interface Health {
  status: string; // "ok"
  time: string; // ISO-8601 UTC
}

/** GET /api/agent */
export interface Agent {
  id: string; // e.g. "AGENT_07"
  name: string;
  area: string;
  providers: Provider[];
}

/**
 * A balance pool. `physical_cash` is the single shared pool (provider null);
 * each provider has one `provider_emoney` pool. Provider separation is absolute —
 * the only shared resource is physical cash.
 */
export interface Pool {
  pool_id: PoolId;
  kind: PoolKind;
  provider: Provider | null;
  label: string;
  balance: number; // integer BDT
  currency: string; // "BDT"
  status: PoolStatus;
}

/**
 * A signed, pool-specific movement. `pool_effects` is the source of truth for how
 * balances move — never reduce a balance without a signed effect.
 * cash_out → physical_cash −amount, provider e-money +amount.
 * cash_in  → physical_cash +amount, provider e-money −amount.
 */
export interface PoolEffect {
  pool_id: PoolId;
  delta: number; // signed integer BDT
}

export interface Transaction {
  id: string;
  ts: string; // ISO-8601 UTC
  provider: Provider;
  txn_type: TxnType;
  amount: number; // always positive; direction lives in pool_effects
  status: TxnStatus;
  account_id: string;
  area: string;
  event_flag?: string | null;
  pool_effects: PoolEffect[];
}

/** Attached to every analytics-bearing response (Phase 1 onward). */
export interface Meta {
  generated_at: string; // ISO-8601 UTC
  data_quality: "ok" | "degraded" | "stale";
  confidence_modifier: number; // < 1.0 when degraded/stale
}

/** GET /api/pools */
export interface PoolsResponse {
  pools: Pool[];
  meta: Meta;
}

/** GET /api/transactions */
export interface TransactionsResponse {
  transactions: Transaction[];
  meta: Meta;
}

// ─── Phase 2 — Liquidity forecast ────────────────────────────────────────────
// Contract base shape: pool_id, current_balance, burn_rate_per_min,
// minutes_to_depletion, projected_depletion_ts, confidence, recommended_action,
// evidence. Extended here with: trend, safety_floor, confidence_factors, history
// (proposed additions — backend must match or the mock adapter bridges the gap).

export type TrendDirection = "accelerating" | "steady" | "easing" | "filling";

/**
 * Describes how the forecast engine classified this pool's outlook.
 * - "projected"        — drain model produced a depletion estimate.
 * - "filling"          — net inflow; no shortage projected (safe/calm).
 * - "insufficient_data"— too few transactions to build a confident model.
 * - "intermittent"     — clumpy/bursty activity; model confidence is reduced.
 * - "at_floor"         — balance is at or below the safety floor.
 */
export type ProjectionState =
  | "projected"
  | "filling"
  | "insufficient_data"
  | "intermittent"
  | "at_floor";

export interface HistoryPoint {
  ts: string;      // ISO-8601 UTC
  balance: number; // integer BDT
}

export interface ConfidenceFactors {
  /** 0–1: share of confidence lost to high volatility */
  volatility: number;
  /** 0–1: how much data the model had (more = better) */
  sample_size: number;
  /** 0–1: how fresh the feed data is (1 = real-time) */
  data_freshness: number;
}

export interface Forecast {
  pool_id: PoolId;
  current_balance: number;
  burn_rate_per_min: number;
  /** null when projection_state is "filling", "insufficient_data", or "intermittent" */
  minutes_to_depletion: number | null;
  /** null when projection_state is not "projected" */
  projected_depletion_ts: string | null;
  /** BDT balance below which operations are constrained */
  safety_floor: number;
  confidence: number; // 0–1
  confidence_factors: ConfidenceFactors;
  trend: TrendDirection;
  /** Classification of the forecast outlook — drives display state. */
  projection_state: ProjectionState;
  recommended_action: string;
  evidence: string[];
  history: HistoryPoint[];
}

export interface ForecastsResponse {
  forecasts: Forecast[];
  meta: Meta;
}

// ─── Phase 3 — Anomaly + liquidity alerts ────────────────────────────────────
// Base contract shape: id, type, severity, label, anomaly_type, provider,
// pool_id, evidence, baseline, observed, confidence, ts, case_id.
// Proposed extensions (confidence_factors, recommended_context) are noted —
// the backend must match these fields or the mock adapter bridges the gap.

export type AlertType = "liquidity" | "anomaly";
export type AlertSeverity = "low" | "medium" | "high";
export type AnomalyType =
  | "structuring"
  | "velocity_spike"
  | "off_hours_burst"
  | "balance_inconsistency";

export interface Alert {
  id: string;
  type: AlertType;
  severity: AlertSeverity;
  label: string;
  anomaly_type: AnomalyType | null;
  provider: Provider | null;
  pool_id: PoolId;
  evidence: string[];
  baseline: Record<string, number | string>;
  observed: Record<string, number | string>;
  confidence: number; // 0–1
  ts: string; // ISO-8601 UTC
  case_id: string | null;
  // Proposed Phase 3 extension fields — not in base contract:
  confidence_factors?: ConfidenceFactors;
  recommended_context?: string;
}

/**
 * Powers the false-positive proof. When a known event (e.g. Eid rush) explains
 * high volume, this is non-null and the UI shows a calm informational chip.
 * Language stays safe — never "fraud" or "suspicious".
 */
export interface AlertContext {
  active_event: string | null;
  note: string;
}

/** GET /api/alerts (Phase 3) */
export interface AlertsResponse {
  alerts: Alert[];
  context: AlertContext | null;
  meta: Meta;
}

// ─── Phase 4 — Case lifecycle ──────────────────────────────────────────────────

export type CaseStatus =
  | "raised"
  | "routed"
  | "acknowledged"
  | "escalated"
  | "resolved";

export type CaseOwnerRole =
  | "field_officer"
  | "risk_reviewer"
  | "supervisor"
  | "area_manager";

export interface CaseEvent {
  stage: CaseStatus;
  actor: string;
  ts: string; // ISO-8601 UTC
  detail: string;
}

/**
 * A coordination case linked to an alert. Carries an immutable audit history.
 * NOTHING here executes a financial action — it notifies, assigns, acknowledges,
 * escalates, recommends, and tracks. Every transition is actor-attributed.
 */
export interface Case {
  id: string;
  alert_id: string;
  type: AlertType;
  provider: Provider | null;
  owner_role: CaseOwnerRole;
  status: CaseStatus;
  escalation_level: number;
  next_step: string;
  recommended_action: string;
  opened_ts: string;
  updated_ts: string;
  sla_minutes: number;
  history: CaseEvent[];
}

/** GET /api/cases */
export interface CasesResponse {
  cases: Case[];
  meta: Meta;
}

/** Body for POST /api/cases/{id}/ack|escalate|resolve */
export interface CaseActionBody {
  actor: string;
  note: string;
}

// ─── Phase 6 — Natural-language explanation (Groq) ───────────────────────────

export type ExplainKind = "forecast" | "alert";
export type ExplainLang = "en" | "bn" | "banglish";

export interface ExplainRequest {
  kind: ExplainKind;
  id: string;
  lang: ExplainLang;
}

/** POST /api/explain → ExplainResponse */
export interface ExplainResponse {
  text: string;
  lang: ExplainLang;
  /** "groq" = LLM-generated; "fallback" = deterministic template. Always shown. */
  source: "groq" | "fallback";
  kind: ExplainKind;
  id: string;
}

// ─── Phase 5 — SSE event payloads ─────────────────────────────────────────────

export interface SimTickEvent {
  sim_time: string;
  tick: number;
}

export interface BalanceUpdateEvent {
  pools: Pool[];
  meta: Meta;
}

export interface ForecastUpdateEvent {
  forecasts: Forecast[];
  meta: Meta;
}

export interface AlertNewEvent {
  alert: Alert;
}

export interface CaseUpdateEvent {
  case: Case;
}

export interface FeedStatusEvent {
  provider: Provider;
  data_quality: "ok" | "degraded" | "stale";
  confidence_modifier: number;
}

/** Tracked per-provider from feed_status SSE events. */
export interface ProviderFeedStatus {
  data_quality: "degraded" | "stale";
  confidence_modifier: number;
}

// ─── Phase 5 — sim control request/response shapes ────────────────────────────

export interface SimStartBody {
  speed?: number;
}

export interface SimEidRushBody {
  provider: PoolId;
  intensity: "low" | "medium" | "high";
}

export interface SimInjectAnomalyBody {
  provider: Provider;
  type: AnomalyType;
}

export interface SimBreakFeedBody {
  provider: Provider;
  mode: "stale" | "degraded";
}

export interface SimRestoreFeedBody {
  provider: Provider;
}

export interface SimControlResponse {
  ok: boolean;
  applied: string;
}
