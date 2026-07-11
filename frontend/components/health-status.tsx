"use client";

import { useEffect, useState } from "react";
import { CircleAlert, CircleCheck, LoaderCircle } from "lucide-react";

import { getHealth, API_BASE_URL } from "@/lib/api";

type State =
  | { kind: "loading" }
  | { kind: "ok"; time: string }
  | { kind: "error"; message: string };

/**
 * Phase 0 proof-of-link: pings the backend /health and renders a themed status
 * chip. Green when connected, danger when unreachable. Fetches client-side so a
 * cold backend never blocks the render.
 */
export function HealthStatus() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let active = true;
    getHealth()
      .then((health) => {
        if (active) setState({ kind: "ok", time: health.time });
      })
      .catch((err: unknown) => {
        if (active)
          setState({
            kind: "error",
            message: err instanceof Error ? err.message : "Unknown error",
          });
      });
    return () => {
      active = false;
    };
  }, []);

  if (state.kind === "loading") {
    return (
      <Chip tone="neutral">
        <LoaderCircle className="size-4 animate-spin" aria-hidden />
        Checking backend…
      </Chip>
    );
  }

  if (state.kind === "ok") {
    return (
      <div className="flex flex-col gap-2">
        <Chip tone="success">
          <CircleCheck className="size-4" aria-hidden />
          Backend connected
        </Chip>
        <p className="text-body-sm text-tertiary tabular-nums-bv">
          Server time {state.time}
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <Chip tone="danger">
        <CircleAlert className="size-4" aria-hidden />
        Backend unreachable
      </Chip>
      <p className="text-body-sm text-tertiary">
        Tried {API_BASE_URL}/health — is the backend running?
      </p>
    </div>
  );
}

// Status chip. Color signals state only (success / danger / neutral) — never
// decoration. Uses a translucent wash of the status color for the pill fill.
function Chip({
  tone,
  children,
}: {
  tone: "success" | "danger" | "neutral";
  children: React.ReactNode;
}) {
  // Opacity modifiers aren't enabled on the tokens (design.md §3), so keep the
  // fill neutral (surface-high) and carry state in the text + border color.
  const toneClass =
    tone === "success"
      ? "text-success border-success bg-surface-high"
      : tone === "danger"
        ? "text-danger border-danger bg-surface-high"
        : "text-secondary border-default bg-surface-high";

  return (
    <span
      className={`inline-flex w-fit items-center gap-2 rounded-pill border px-3 py-1.5 text-label-md ${toneClass}`}
    >
      {children}
    </span>
  );
}
