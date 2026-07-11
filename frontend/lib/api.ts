// Typed API client for the ProhoriPay backend. Base URL comes from the
// NEXT_PUBLIC_API_BASE_URL env var (see .env.local.example). Build to
// shared/contract.md — do not invent divergent request/response shapes.

import type {
  Agent,
  Health,
  PoolsResponse,
  TransactionsResponse,
  Provider,
} from "./types";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

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
  } catch (cause) {
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
export function getAgent(): Promise<Agent> {
  return request<Agent>("/api/agent");
}

/** GET /api/pools (Phase 1) */
export function getPools(): Promise<PoolsResponse> {
  return request<PoolsResponse>("/api/pools");
}

/** GET /api/transactions (Phase 1) */
export function getTransactions(params?: {
  limit?: number;
  provider?: Provider;
}): Promise<TransactionsResponse> {
  const search = new URLSearchParams();
  if (params?.limit != null) search.set("limit", String(params.limit));
  if (params?.provider) search.set("provider", params.provider);
  const qs = search.toString();
  return request<TransactionsResponse>(
    `/api/transactions${qs ? `?${qs}` : ""}`,
  );
}
