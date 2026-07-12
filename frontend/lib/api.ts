// Typed API client for the ProhoriPay backend. Base URL comes from the
// NEXT_PUBLIC_API_BASE_URL env var (see .env.local.example). Build to
// shared/contract.md — do not invent divergent request/response shapes.

import type {
  Agent,
  AlertsResponse,
  Health,
  PoolsResponse,
  TransactionsResponse,
  ForecastsResponse,
  Provider,
  Case,
  CasesResponse,
  CaseActionBody,
  SimStartBody,
  SimEidRushBody,
  SimInjectAnomalyBody,
  SimBreakFeedBody,
  SimRestoreFeedBody,
  SimControlResponse,
  ExplainRequest,
  ExplainResponse,
  PatchCashBody,
  PatchCashResponse,
} from "./types";
import {
  getMockAgent,
  getMockAlerts,
  getMockPools,
  getMockTransactions,
  getMockForecasts,
  getMockCases,
  getMockCase,
  mockAckCase,
  mockEscalateCase,
  mockResolveCase,
  getMockExplain,
} from "./mock";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

/**
 * Set NEXT_PUBLIC_USE_MOCK=true in .env.local to build against the mock adapter.
 * Flip to false (or unset) once the backend Phase 1 is running.
 */
export const USE_MOCK =
  process.env.NEXT_PUBLIC_USE_MOCK === "true";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      // Advisory decision-support data is read-only and time-sensitive; never cache.
      cache: "no-store",
      headers: { Accept: "application/json" },
      ...init,
    });
  } catch {
    throw new ApiError(
      `Cannot reach backend at ${API_BASE_URL}${path}`,
    );
  }
  if (!res.ok) {
    throw new ApiError(`Request failed: ${path}`, res.status);
  }
  return (await res.json()) as T;
}

/** GET /health — liveness probe used by the Phase 0 status chip. */
export function getHealth(): Promise<Health> {
  return request<Health>("/health");
}

/** GET /api/agent (Phase 1) */
export async function getAgent(): Promise<Agent> {
  if (USE_MOCK) return getMockAgent();
  return request<Agent>("/api/agent");
}

/** GET /api/pools (Phase 1) */
export async function getPools(): Promise<PoolsResponse> {
  if (USE_MOCK) return getMockPools();
  return request<PoolsResponse>("/api/pools");
}

/** GET /api/forecast (Phase 2) */
export async function getForecast(): Promise<ForecastsResponse> {
  if (USE_MOCK) return getMockForecasts();
  return request<ForecastsResponse>("/api/forecast");
}

/** GET /api/alerts (Phase 3) */
export async function getAlerts(): Promise<AlertsResponse> {
  if (USE_MOCK) return getMockAlerts();
  return request<AlertsResponse>("/api/alerts");
}

/** GET /api/cases (Phase 4) */
export async function getCases(params?: {
  status?: string;
  provider?: string;
}): Promise<CasesResponse> {
  if (USE_MOCK) return getMockCases(params);
  const search = new URLSearchParams();
  if (params?.status) search.set("status", params.status);
  if (params?.provider) search.set("provider", params.provider);
  const qs = search.toString();
  return request<CasesResponse>(`/api/cases${qs ? `?${qs}` : ""}`);
}

/** GET /api/cases/{id} (Phase 4) */
export async function getCase(id: string): Promise<Case> {
  if (USE_MOCK) return getMockCase(id);
  return request<Case>(`/api/cases/${id}`);
}

/** POST /api/cases/{id}/ack (Phase 4) */
export async function ackCase(
  id: string,
  body: CaseActionBody
): Promise<Case> {
  if (USE_MOCK) return mockAckCase(id, body);
  return request<Case>(`/api/cases/${id}/ack`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

/** POST /api/cases/{id}/escalate (Phase 4) */
export async function escalateCase(
  id: string,
  body: CaseActionBody
): Promise<Case> {
  if (USE_MOCK) return mockEscalateCase(id, body);
  return request<Case>(`/api/cases/${id}/escalate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

/** POST /api/cases/{id}/resolve (Phase 4) */
export async function resolveCase(
  id: string,
  body: CaseActionBody
): Promise<Case> {
  if (USE_MOCK) return mockResolveCase(id, body);
  return request<Case>(`/api/cases/${id}/resolve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

// ─── Phase 5 — Simulation controls ───────────────────────────────────────────

async function simPost<B>(path: string, body?: B): Promise<SimControlResponse> {
  if (USE_MOCK) {
    // Mock mode: sim controls can't drive the SSE stream, but we return a
    // plausible response so the demo panel buttons give feedback.
    const label = path.replace("/api/sim/", "");
    const bodyStr = body && Object.keys(body as object).length
      ? " — " + JSON.stringify(body)
      : "";
    return { ok: true, applied: `[mock] ${label}${bodyStr}` };
  }
  return request<SimControlResponse>(path, {
    method: "POST",
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
}

export const simStart = (body: SimStartBody = {}) =>
  simPost("/api/sim/start", body);

export const simPause = () =>
  simPost("/api/sim/pause");

export const simReset = () =>
  simPost("/api/sim/reset");

export const simEidRush = (body: SimEidRushBody) =>
  simPost("/api/sim/eid_rush", body);

export const simInjectAnomaly = (body: SimInjectAnomalyBody) =>
  simPost("/api/sim/inject_anomaly", body);

export const simBreakFeed = (body: SimBreakFeedBody) =>
  simPost("/api/sim/break_feed", body);

export const simRestoreFeed = (body: SimRestoreFeedBody) =>
  simPost("/api/sim/restore_feed", body);

// ─── Physical cash count — human-recorded ────────────────────────────────────

/**
 * PATCH /api/pools/physical_cash — agent records the actual cash in the drawer.
 * Advisory only: this records what the human counted; no automatic action.
 */
export async function patchPhysicalCash(
  body: PatchCashBody
): Promise<PatchCashResponse> {
  if (USE_MOCK) {
    return { ok: true, pool_id: "physical_cash", balance: body.balance, note: body.note ?? null };
  }
  return request<PatchCashResponse>("/api/pools/physical_cash", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

// ─── Phase 6 — Natural-language explanation ───────────────────────────────────

/**
 * POST /api/explain — returns an EN/বাংলা/Banglish plain-language explanation of
 * an alert or forecast. Falls back to a deterministic template if Groq is
 * unavailable. Source is always declared ("groq" | "fallback").
 */
export async function explain(req: ExplainRequest): Promise<ExplainResponse> {
  if (USE_MOCK) return getMockExplain(req);
  return request<ExplainResponse>("/api/explain", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
}

// ─── Phase 1 — Transactions ───────────────────────────────────────────────────

/** GET /api/transactions (Phase 1) */
export async function getTransactions(params?: {
  limit?: number;
  provider?: Provider;
}): Promise<TransactionsResponse> {
  if (USE_MOCK) return getMockTransactions(params);
  const search = new URLSearchParams();
  if (params?.limit != null) search.set("limit", String(params.limit));
  if (params?.provider) search.set("provider", params.provider);
  const qs = search.toString();
  return request<TransactionsResponse>(
    `/api/transactions${qs ? `?${qs}` : ""}`,
  );
}
