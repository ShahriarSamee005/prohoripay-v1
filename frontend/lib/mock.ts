/**
 * Mock adapter — returns contract-shaped data so the UI can be built and
 * verified independently before the backend is running.
 *
 * Includes the hidden-shortage scenario: total holdings look large, but
 * physical_cash is "critical" (the constraining pool). The hero MUST surface
 * this — showing only the aggregate would mask the operational risk.
 */
import type {
  Agent,
  Alert,
  AlertContext,
  AlertsResponse,
  Pool,
  Transaction,
  PoolsResponse,
  TransactionsResponse,
  ForecastsResponse,
  Forecast,
  Meta,
} from "./types";

const MOCK_META_OK: Meta = {
  generated_at: "2026-07-11T09:00:00Z",
  data_quality: "ok",
  confidence_modifier: 1.0,
};

export const MOCK_AGENT: Agent = {
  id: "AGENT_07",
  name: "Karim Store",
  area: "Sylhet-Zindabazar",
  providers: ["bkash", "nagad", "rocket"],
};

/**
 * Hidden-shortage scenario:
 *   physical_cash = 4 200 BDT  → critical   ← constraining pool
 *   bkash        = 42 500 BDT  → healthy
 *   nagad        = 31 000 BDT  → healthy
 *   rocket       = 18 800 BDT  → watch
 *   total        = 96 500 BDT  (sum label only — NOT spendable)
 */
export const MOCK_POOLS: Pool[] = [
  {
    pool_id: "physical_cash",
    kind: "physical_cash",
    provider: null,
    label: "Physical Cash",
    balance: 4200,
    currency: "BDT",
    status: "critical",
  },
  {
    pool_id: "bkash",
    kind: "provider_emoney",
    provider: "bkash",
    label: "bKash",
    balance: 42500,
    currency: "BDT",
    status: "healthy",
  },
  {
    pool_id: "nagad",
    kind: "provider_emoney",
    provider: "nagad",
    label: "Nagad",
    balance: 31000,
    currency: "BDT",
    status: "healthy",
  },
  {
    pool_id: "rocket",
    kind: "provider_emoney",
    provider: "rocket",
    label: "Rocket",
    balance: 18800,
    currency: "BDT",
    status: "watch",
  },
];

export const MOCK_TRANSACTIONS: Transaction[] = [
  {
    id: "txn_00001",
    ts: "2026-07-11T09:14:00Z",
    provider: "bkash",
    txn_type: "cash_out",
    amount: 9500,
    status: "completed",
    account_id: "ACC_1034",
    area: "Sylhet-Zindabazar",
    event_flag: "eid_rush",
    pool_effects: [
      { pool_id: "physical_cash", delta: -9500 },
      { pool_id: "bkash", delta: 9500 },
    ],
  },
  {
    id: "txn_00002",
    ts: "2026-07-11T09:10:00Z",
    provider: "bkash",
    txn_type: "cash_in",
    amount: 5000,
    status: "completed",
    account_id: "ACC_1021",
    area: "Sylhet-Zindabazar",
    event_flag: null,
    pool_effects: [
      { pool_id: "physical_cash", delta: 5000 },
      { pool_id: "bkash", delta: -5000 },
    ],
  },
  {
    id: "txn_00003",
    ts: "2026-07-11T09:05:00Z",
    provider: "nagad",
    txn_type: "cash_out",
    amount: 12000,
    status: "completed",
    account_id: "ACC_2047",
    area: "Sylhet-Zindabazar",
    event_flag: null,
    pool_effects: [
      { pool_id: "physical_cash", delta: -12000 },
      { pool_id: "nagad", delta: 12000 },
    ],
  },
  {
    id: "txn_00004",
    ts: "2026-07-11T08:58:00Z",
    provider: "rocket",
    txn_type: "cash_out",
    amount: 3200,
    status: "pending",
    account_id: "ACC_3011",
    area: "Sylhet-Zindabazar",
    event_flag: null,
    pool_effects: [
      { pool_id: "physical_cash", delta: -3200 },
      { pool_id: "rocket", delta: 3200 },
    ],
  },
  {
    id: "txn_00005",
    ts: "2026-07-11T08:50:00Z",
    provider: "nagad",
    txn_type: "cash_in",
    amount: 8000,
    status: "completed",
    account_id: "ACC_2099",
    area: "Sylhet-Zindabazar",
    event_flag: null,
    pool_effects: [
      { pool_id: "physical_cash", delta: 8000 },
      { pool_id: "nagad", delta: -8000 },
    ],
  },
  {
    id: "txn_00006",
    ts: "2026-07-11T08:42:00Z",
    provider: "bkash",
    txn_type: "cash_out",
    amount: 9500,
    status: "completed",
    account_id: "ACC_1034",
    area: "Sylhet-Zindabazar",
    event_flag: "eid_rush",
    pool_effects: [
      { pool_id: "physical_cash", delta: -9500 },
      { pool_id: "bkash", delta: 9500 },
    ],
  },
  {
    id: "txn_00007",
    ts: "2026-07-11T08:35:00Z",
    provider: "rocket",
    txn_type: "cash_in",
    amount: 6500,
    status: "completed",
    account_id: "ACC_3055",
    area: "Sylhet-Zindabazar",
    event_flag: null,
    pool_effects: [
      { pool_id: "physical_cash", delta: 6500 },
      { pool_id: "rocket", delta: -6500 },
    ],
  },
  {
    id: "txn_00008",
    ts: "2026-07-11T08:20:00Z",
    provider: "bkash",
    txn_type: "cash_out",
    amount: 9500,
    status: "failed",
    account_id: "ACC_1078",
    area: "Sylhet-Zindabazar",
    event_flag: "eid_rush",
    pool_effects: [
      { pool_id: "physical_cash", delta: 0 },
      { pool_id: "bkash", delta: 0 },
    ],
  },
];

// ─── Phase 2 mock forecasts ───────────────────────────────────────────────────
// Four trend cases: accelerating (physical_cash), filling (bkash),
// steady (nagad), easing (rocket). History = 13 pts, every 5 min, 08:00–09:00Z.

function historyTs(minutesBack: number): string {
  // Reference "now" = 2026-07-11T09:00:00Z
  const base = new Date("2026-07-11T09:00:00Z");
  base.setMinutes(base.getMinutes() - minutesBack);
  return base.toISOString().replace(".000", "");
}

const PHYSICAL_CASH_HISTORY = [
  9200, 9000, 8760, 8480, 8160, 7800, 7400, 6960, 6480, 5960, 5400, 4800, 4200,
].map((balance, i) => ({ ts: historyTs(60 - i * 5), balance }));

const BKASH_HISTORY = [
  34500, 35100, 35700, 36200, 36700, 37200, 37700, 38200, 38700, 39200, 40000, 41200, 42500,
].map((balance, i) => ({ ts: historyTs(60 - i * 5), balance }));

const NAGAD_HISTORY = [
  32500, 32375, 32250, 32125, 32000, 31875, 31750, 31625, 31500, 31375, 31250, 31125, 31000,
].map((balance, i) => ({ ts: historyTs(60 - i * 5), balance }));

const ROCKET_HISTORY = [
  24300, 23750, 23200, 22650, 22200, 21750, 21350, 20950, 20600, 20250, 19900, 19350, 18800,
].map((balance, i) => ({ ts: historyTs(60 - i * 5), balance }));

export const MOCK_FORECASTS: Forecast[] = [
  {
    // physical_cash: critical, accelerating. ~28 min to safety floor.
    pool_id: "physical_cash",
    current_balance: 4200,
    burn_rate_per_min: 120,
    minutes_to_depletion: 18,
    projected_depletion_ts: "2026-07-11T09:18:00Z",
    safety_floor: 2000,
    confidence: 0.88,
    confidence_factors: { volatility: 0.35, sample_size: 0.85, data_freshness: 0.95 },
    trend: "accelerating",
    recommended_action:
      "Request physical cash top-up from the nearest distributor or consider pausing cash-out services temporarily until replenished.",
    evidence: [
      "Cash-out rate has accelerated from 40 BDT/min to 120 BDT/min over the last hour",
      "Balance fell ৳9,200 → ৳4,200 in 60 minutes",
      "Eid Rush event flag active — demand spike likely to continue",
    ],
    history: PHYSICAL_CASH_HISTORY,
  },
  {
    // bkash: filling — no shortage projected.
    pool_id: "bkash",
    current_balance: 42500,
    burn_rate_per_min: -90,
    minutes_to_depletion: null,
    projected_depletion_ts: null,
    safety_floor: 5000,
    confidence: 0.91,
    confidence_factors: { volatility: 0.15, sample_size: 0.90, data_freshness: 1.0 },
    trend: "filling",
    recommended_action:
      "bKash e-money balance is growing. No top-up needed. Monitor physical cash — it remains the constraining pool.",
    evidence: [
      "Net cash-in inflow of ~90 BDT/min over the last hour",
      "Balance grew ৳34,500 → ৳42,500 in 60 minutes",
      "High customer deposit activity consistent with festival season",
    ],
    history: BKASH_HISTORY,
  },
  {
    // nagad: steady drain, well above floor.
    pool_id: "nagad",
    current_balance: 31000,
    burn_rate_per_min: 25,
    minutes_to_depletion: 1040,
    projected_depletion_ts: "2026-07-12T01:20:00Z",
    safety_floor: 5000,
    confidence: 0.79,
    confidence_factors: { volatility: 0.20, sample_size: 0.72, data_freshness: 0.88 },
    trend: "steady",
    recommended_action:
      "Nagad balance is draining at a low, steady rate. No immediate action needed — reassess in 4–6 hours.",
    evidence: [
      "Consistent 25 BDT/min net outflow over the last hour",
      "Balance fell ৳32,500 → ৳31,000 in 60 minutes",
      "No unusual spikes; transaction mix is normal",
    ],
    history: NAGAD_HISTORY,
  },
  {
    // rocket: was draining fast, now easing.
    pool_id: "rocket",
    current_balance: 18800,
    burn_rate_per_min: 35,
    minutes_to_depletion: 451,
    projected_depletion_ts: "2026-07-11T16:31:00Z",
    safety_floor: 3000,
    confidence: 0.74,
    confidence_factors: { volatility: 0.42, sample_size: 0.68, data_freshness: 0.90 },
    trend: "easing",
    recommended_action:
      "Rocket drain rate is easing. Watch for recurrence — consider a modest top-up if the easing reverses within the next 2 hours.",
    evidence: [
      "Drain rate fell from ~110 BDT/min (08:00) to ~35 BDT/min (09:00)",
      "Balance fell ৳24,300 → ৳18,800 in 60 minutes",
      "Confidence reduced: high volatility in this window",
    ],
    history: ROCKET_HISTORY,
  },
];

// ─── Phase 3 mock alerts ─────────────────────────────────────────────────────
// Mix: structuring anomaly (high, full evidence), velocity_spike (medium),
// physical_cash liquidity alert (high). Context: Eid demand recognised as
// expected — demonstrates false-positive suppression.

export const MOCK_ALERTS: Alert[] = [
  {
    // Structuring: repeated amounts just below threshold from multiple accounts
    id: "alert_0001",
    type: "anomaly",
    severity: "high",
    label: "unusual — requires review",
    anomaly_type: "structuring",
    provider: "bkash",
    pool_id: "bkash",
    evidence: [
      "12 transactions of ~9,500 BDT",
      "From 3 accounts",
      "Within 45 minutes",
      "Amounts consistently near ৳10,000 threshold",
      "Pattern not seen in 7-day baseline",
    ],
    baseline: { txn_per_min: 2, amount_avg: 5200 },
    observed: { txn_per_min: 15, amount_avg: 9480 },
    confidence: 0.83,
    ts: "2026-07-11T09:14:00Z",
    case_id: null,
    confidence_factors: { volatility: 0.25, sample_size: 0.88, data_freshness: 0.97 },
    recommended_context:
      "Review the 12 transactions listed above. Check if these accounts are known to this agent. Consider escalating to a risk reviewer if the pattern repeats.",
  },
  {
    // Velocity spike: sudden burst in Nagad transaction rate with no known event
    id: "alert_0002",
    type: "anomaly",
    severity: "medium",
    label: "unusual — requires review",
    anomaly_type: "velocity_spike",
    provider: "nagad",
    pool_id: "nagad",
    evidence: [
      "Transaction rate spiked from 3/min to 22/min",
      "18 unique accounts in 20 minutes",
      "Unusual for this time of day",
      "No known event flag for this window",
    ],
    baseline: { txn_per_min: 3, unique_accounts_per_20min: 5 },
    observed: { txn_per_min: 22, unique_accounts_per_20min: 18 },
    confidence: 0.71,
    ts: "2026-07-11T09:08:00Z",
    case_id: null,
    confidence_factors: { volatility: 0.38, sample_size: 0.75, data_freshness: 0.92 },
    recommended_context:
      "Check whether a local event or Nagad promotion explains the sudden increase. If no event context, review the transaction origins.",
  },
  {
    // Liquidity: physical cash critically low, derived from Phase-2 forecast
    id: "alert_0003",
    type: "liquidity",
    severity: "high",
    label: "liquidity pressure — requires attention",
    anomaly_type: null,
    provider: null,
    pool_id: "physical_cash",
    evidence: [
      "Physical cash at ৳4,200 — below safe operating floor",
      "Burn rate: 120 BDT/min (accelerating)",
      "Projected depletion in ~18 minutes",
      "Eid Rush event active — demand spike likely to continue",
    ],
    baseline: { balance_floor: 10000, burn_rate_per_min: 40 },
    observed: { balance_current: 4200, burn_rate_per_min: 120 },
    confidence: 0.88,
    ts: "2026-07-11T09:00:00Z",
    case_id: null,
    confidence_factors: { volatility: 0.35, sample_size: 0.85, data_freshness: 0.95 },
    recommended_context:
      "Request physical cash top-up from the nearest distributor. Consider temporarily pausing cash-out services until replenished.",
  },
];

/** Context proving false-positive control: Eid demand explains the volume spike */
export const MOCK_ALERT_CONTEXT: AlertContext = {
  active_event: "eid_rush",
  note: "High volume recognized as Eid demand — treated as expected",
};

export function getMockAlerts(): AlertsResponse {
  return {
    alerts: MOCK_ALERTS,
    context: MOCK_ALERT_CONTEXT,
    meta: MOCK_META_OK,
  };
}

export function getMockAgent(): Agent {
  return MOCK_AGENT;
}

export function getMockPools(): PoolsResponse {
  return { pools: MOCK_POOLS, meta: MOCK_META_OK };
}

export function getMockForecasts(): ForecastsResponse {
  return { forecasts: MOCK_FORECASTS, meta: MOCK_META_OK };
}

export function getMockTransactions(params?: {
  limit?: number;
  provider?: string;
}): TransactionsResponse {
  let txns = MOCK_TRANSACTIONS;
  if (params?.provider) {
    txns = txns.filter((t) => t.provider === params.provider);
  }
  if (params?.limit != null) {
    txns = txns.slice(0, params.limit);
  }
  return { transactions: txns, meta: MOCK_META_OK };
}
