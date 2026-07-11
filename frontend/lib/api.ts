// Typed API client for the ProhoriPay backend. Base URL comes from the
// NEXT_PUBLIC_API_BASE_URL env var (see .env.local.example). Build to
// shared/contract.md — do not invent divergent request/response shapes.

import type {
  Agent,
  Health,
  PoolsResponse,
  TransactionsResponse,
  ForecastsResponse,
  Provider,
} from "./types";
import {
  getMockAgent,
  getMockPools,
  getMockTransactions,
  getMockForecasts,
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
