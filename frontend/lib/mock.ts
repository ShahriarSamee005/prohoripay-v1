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
  Pool,
  Transaction,
  PoolsResponse,
  TransactionsResponse,
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

export function getMockAgent(): Agent {
  return MOCK_AGENT;
}

export function getMockPools(): PoolsResponse {
  return { pools: MOCK_POOLS, meta: MOCK_META_OK };
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
