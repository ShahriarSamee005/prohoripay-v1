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
  /** null when trend is "filling" — no shortage projected */
  minutes_to_depletion: number | null;
  /** null when trend is "filling" */
  projected_depletion_ts: string | null;
  /** BDT balance below which operations are constrained */
  safety_floor: number;
  confidence: number; // 0–1
  confidence_factors: ConfidenceFactors;
  trend: TrendDirection;
  recommended_action: string;
  evidence: string[];
  history: HistoryPoint[];
}

export interface ForecastsResponse {
  forecasts: Forecast[];
  meta: Meta;
}
