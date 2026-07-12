// SSE client for the Phase 5 live stream (GET /api/stream).
// Each named event maps to a typed callback. On reconnect, the caller should
// re-fetch REST snapshots to fill any gap before resuming SSE updates.

import { API_BASE_URL } from "./api";
import type {
  SimTickEvent,
  BalanceUpdateEvent,
  ForecastUpdateEvent,
  AlertNewEvent,
  CaseUpdateEvent,
  FeedStatusEvent,
} from "./types";

export interface StreamCallbacks {
  onTick?: (ev: SimTickEvent) => void;
  onBalanceUpdate?: (ev: BalanceUpdateEvent) => void;
  onForecastUpdate?: (ev: ForecastUpdateEvent) => void;
  onAlertNew?: (ev: AlertNewEvent) => void;
  onCaseUpdate?: (ev: CaseUpdateEvent) => void;
  onFeedStatus?: (ev: FeedStatusEvent) => void;
  onConnected?: () => void;
  onDisconnected?: () => void;
}

function parseSafe<T>(data: string): T | null {
  try {
    return JSON.parse(data) as T;
  } catch {
    return null;
  }
}

/**
 * Subscribe to the SSE stream. Returns an unsubscribe function.
 * Automatically reconnects after 3 s on error/close. Each reconnect
 * fires onConnected so the caller can re-fetch REST snapshots.
 */
export function subscribeToStream(callbacks: StreamCallbacks): () => void {
  let es: EventSource | null = null;
  let stopped = false;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  function connect() {
    if (stopped) return;

    es = new EventSource(`${API_BASE_URL}/api/stream`);

    es.onopen = () => {
      callbacks.onConnected?.();
    };

    es.onerror = () => {
      callbacks.onDisconnected?.();
      es?.close();
      es = null;
      if (!stopped) {
        reconnectTimer = setTimeout(connect, 3000);
      }
    };

    es.addEventListener("tick", (raw) => {
      const ev = parseSafe<SimTickEvent>((raw as MessageEvent).data);
      if (ev) callbacks.onTick?.(ev);
    });

    es.addEventListener("balance_update", (raw) => {
      const ev = parseSafe<BalanceUpdateEvent>((raw as MessageEvent).data);
      if (ev) callbacks.onBalanceUpdate?.(ev);
    });

    es.addEventListener("forecast_update", (raw) => {
      const ev = parseSafe<ForecastUpdateEvent>((raw as MessageEvent).data);
      if (ev) callbacks.onForecastUpdate?.(ev);
    });

    es.addEventListener("alert_new", (raw) => {
      const ev = parseSafe<AlertNewEvent>((raw as MessageEvent).data);
      if (ev) callbacks.onAlertNew?.(ev);
    });

    es.addEventListener("case_update", (raw) => {
      const ev = parseSafe<CaseUpdateEvent>((raw as MessageEvent).data);
      if (ev) callbacks.onCaseUpdate?.(ev);
    });

    es.addEventListener("feed_status", (raw) => {
      const ev = parseSafe<FeedStatusEvent>((raw as MessageEvent).data);
      if (ev) callbacks.onFeedStatus?.(ev);
    });
  }

  connect();

  return () => {
    stopped = true;
    if (reconnectTimer !== null) clearTimeout(reconnectTimer);
    es?.close();
    es = null;
  };
}
