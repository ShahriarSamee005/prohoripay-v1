"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle, AlertTriangle, XCircle, Clock, User, ArrowUp } from "lucide-react";
import type { Case, CaseStatus, CaseOwnerRole, CaseEvent } from "@/lib/types";
import { ackCase, escalateCase, resolveCase } from "@/lib/api";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fmtTime(ts: string): string {
  return ts.substring(11, 16) + " UTC";
}

function ownerRoleLabel(role: CaseOwnerRole): string {
  const m: Record<CaseOwnerRole, string> = {
    field_officer: "Field Officer",
    risk_reviewer: "Risk Reviewer",
    supervisor: "Supervisor",
    area_manager: "Area Manager",
  };
  return m[role];
}

function stageLabel(stage: CaseStatus): string {
  const m: Record<CaseStatus, string> = {
    raised: "Raised",
    routed: "Routed",
    acknowledged: "Acknowledged",
    escalated: "Escalated",
    resolved: "Resolved",
  };
  return m[stage];
}

function StatusPill({ status }: { status: CaseStatus }) {
  const styles: Record<CaseStatus, string> = {
    raised: "bg-surface-high text-secondary",
    routed: "bg-surface-high text-warning border border-warning",
    acknowledged: "bg-brand text-on-brand",
    escalated: "bg-danger text-on-brand",
    resolved: "bg-success text-on-brand",
  };
  // bg-danger/bg-success aren't semantic Tailwind classes — use inline style trick with var
  const inlineStyles: Record<CaseStatus, React.CSSProperties> = {
    raised: {},
    routed: {},
    acknowledged: {},
    escalated: { backgroundColor: "var(--bv-danger)", color: "#fff" },
    resolved: { backgroundColor: "var(--bv-success)", color: "#fff" },
  };
  const base =
    status === "acknowledged"
      ? "px-2.5 py-0.5 rounded-pill text-label-sm bg-brand text-on-brand"
      : status === "escalated" || status === "resolved"
        ? "px-2.5 py-0.5 rounded-pill text-label-sm"
        : `px-2.5 py-0.5 rounded-pill text-label-sm ${styles[status]}`;

  return (
    <span className={base} style={inlineStyles[status]}>
      {stageLabel(status)}
    </span>
  );
}

// ─── Audit timeline ───────────────────────────────────────────────────────────

const STAGE_DOT_COLOR: Record<CaseStatus, string> = {
  raised: "var(--bv-text-tertiary)",
  routed: "var(--bv-warning)",
  acknowledged: "var(--bv-brand)",
  escalated: "var(--bv-danger)",
  resolved: "var(--bv-success)",
};

function TimelineDot({ stage, isLast }: { stage: CaseStatus; isLast: boolean }) {
  return (
    <div className="relative flex flex-col items-center shrink-0" style={{ width: 24 }}>
      <div
        className="size-3 rounded-pill z-10 mt-0.5 shrink-0"
        style={{ backgroundColor: STAGE_DOT_COLOR[stage] }}
      />
      {!isLast && (
        <div
          className="w-px flex-1 mt-1"
          style={{ backgroundColor: "var(--bv-border)", minHeight: 16 }}
        />
      )}
    </div>
  );
}

function AuditTimeline({ history }: { history: CaseEvent[] }) {
  if (history.length === 0) return null;
  return (
    <div>
      <p className="text-label-sm text-secondary mb-3">Audit Timeline</p>
      <div className="space-y-0">
        {history.map((event, i) => (
          <div key={i} className="flex gap-3">
            <TimelineDot stage={event.stage} isLast={i === history.length - 1} />
            <div className="pb-3 flex-1 min-w-0">
              <div className="flex items-baseline gap-2 flex-wrap">
                <span
                  className="text-label-sm font-semibold"
                  style={{ color: STAGE_DOT_COLOR[event.stage] }}
                >
                  {stageLabel(event.stage)}
                </span>
                <span className="text-body-sm text-secondary">
                  {event.actor} · {fmtTime(event.ts)}
                </span>
              </div>
              {event.detail && (
                <p className="text-body-sm text-tertiary mt-0.5">{event.detail}</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Action buttons ───────────────────────────────────────────────────────────

interface ActionButtonProps {
  label: string;
  enabled: boolean;
  variant: "primary" | "warn" | "success";
  loading: boolean;
  onClick: () => void;
}

function ActionButton({ label, enabled, variant, loading, onClick }: ActionButtonProps) {
  const base =
    "px-4 py-2 rounded-md text-label-sm transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2";
  const variants: Record<string, string> = {
    primary: "bg-brand text-on-brand hover:bg-brand-deep focus-visible:outline-brand",
    warn: "border border-default text-warning hover:bg-surface-high focus-visible:outline-brand",
    success: "border border-default text-success hover:bg-surface-high focus-visible:outline-brand",
  };
  return (
    <button
      onClick={onClick}
      disabled={!enabled || loading}
      className={`${base} ${variants[variant]} disabled:opacity-40 disabled:cursor-not-allowed`}
    >
      {loading ? "…" : label}
    </button>
  );
}

// ─── Resolve note field ───────────────────────────────────────────────────────

function ResolveNoteField({
  note,
  onChange,
  onConfirm,
  onCancel,
  loading,
}: {
  note: string;
  onChange: (v: string) => void;
  onConfirm: () => void;
  onCancel: () => void;
  loading: boolean;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: "auto" }}
      exit={{ opacity: 0, height: 0 }}
      className="space-y-2 overflow-hidden"
    >
      <p className="text-label-sm text-secondary">Reason for resolution</p>
      <textarea
        value={note}
        onChange={(e) => onChange(e.target.value)}
        placeholder="e.g. reviewed — confirmed salary payment batch"
        rows={2}
        className="w-full rounded-md border border-default bg-surface-high px-3 py-2 text-body-sm text-primary placeholder:text-tertiary resize-none focus:outline-none focus:ring-2 focus:ring-brand"
      />
      <div className="flex gap-2">
        <button
          onClick={onConfirm}
          disabled={!note.trim() || loading}
          className="px-4 py-1.5 rounded-md bg-brand text-on-brand text-label-sm transition-colors hover:bg-brand-deep disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {loading ? "…" : "Confirm resolution"}
        </button>
        <button
          onClick={onCancel}
          className="px-4 py-1.5 rounded-md border border-default text-secondary text-label-sm hover:bg-surface-high"
        >
          Cancel
        </button>
      </div>
    </motion.div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

interface CasePanelProps {
  case_: Case | null;
  onUpdate: (updated: Case) => void;
}

export function CasePanel({ case_, onUpdate }: CasePanelProps) {
  const [isActing, setIsActing] = useState(false);
  const [showResolveField, setShowResolveField] = useState(false);
  const [resolveNote, setResolveNote] = useState("");
  const [error, setError] = useState<string | null>(null);

  if (!case_) {
    return (
      <div className="rounded-lg border border-default bg-surface-high p-4">
        <p className="text-body-sm text-tertiary">No coordination case linked to this alert.</p>
      </div>
    );
  }

  const { status } = case_;
  const canAck = status === "routed";
  const canEscalate = status === "acknowledged";
  const canResolve = status === "acknowledged" || status === "escalated";
  const isResolved = status === "resolved";

  async function handleAck() {
    setIsActing(true);
    setError(null);
    try {
      const updated = await ackCase(case_!.id, {
        actor: case_!.owner_role,
        note: "",
      });
      onUpdate(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Action failed — please try again");
    } finally {
      setIsActing(false);
    }
  }

  async function handleEscalate() {
    setIsActing(true);
    setError(null);
    try {
      const updated = await escalateCase(case_!.id, {
        actor: case_!.owner_role,
        note: "",
      });
      onUpdate(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Action failed — please try again");
    } finally {
      setIsActing(false);
    }
  }

  async function handleResolveClick() {
    if (!showResolveField) {
      setShowResolveField(true);
      return;
    }
  }

  async function handleResolveConfirm() {
    if (!resolveNote.trim()) return;
    setIsActing(true);
    setError(null);
    try {
      const updated = await resolveCase(case_!.id, {
        actor: case_!.owner_role,
        note: resolveNote.trim(),
      });
      onUpdate(updated);
      setShowResolveField(false);
      setResolveNote("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Action failed — please try again");
    } finally {
      setIsActing(false);
    }
  }

  return (
    <div className="space-y-4">
      {/* Section label */}
      <div className="flex items-center gap-2">
        <div className="h-px flex-1 bg-surface-high" />
        <span className="text-label-sm text-tertiary uppercase tracking-wide px-1">
          Coordination
        </span>
        <div className="h-px flex-1 bg-surface-high" />
      </div>

      {/* Header: owner, status, SLA, provider */}
      <div className="bg-surface-high rounded-lg p-3.5 space-y-2.5">
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-2">
            <User className="size-4 text-tertiary shrink-0" />
            <span className="text-title-sm text-primary">
              {ownerRoleLabel(case_.owner_role)}
            </span>
            {case_.escalation_level > 0 && (
              <span className="flex items-center gap-0.5 text-label-sm text-warning">
                <ArrowUp className="size-3" />
                L{case_.escalation_level}
              </span>
            )}
          </div>
          <StatusPill status={status} />
        </div>

        <div className="flex items-center gap-3 flex-wrap text-body-sm text-secondary">
          <span className="flex items-center gap-1">
            <Clock className="size-3.5 text-tertiary" />
            SLA {case_.sla_minutes} min
          </span>
          {case_.provider && (
            <span className="capitalize">{case_.provider}</span>
          )}
          {!case_.provider && case_.type === "liquidity" && (
            <span>Physical Cash</span>
          )}
          <span className="text-tertiary">Case {case_.id}</span>
        </div>
      </div>

      {/* Recommended next step (prominent) */}
      {case_.next_step && (
        <div>
          <p className="text-label-sm text-secondary mb-1.5">Next Step</p>
          <p className="text-title-sm text-primary">{case_.next_step}</p>
        </div>
      )}

      {/* Recommended action (advisory language) */}
      <div className="rounded-lg border border-default p-3.5 space-y-1">
        <p className="text-label-sm text-secondary">Recommended Action</p>
        <p className="text-body-sm text-primary">{case_.recommended_action}</p>
      </div>

      {/* Action buttons */}
      {!isResolved && (
        <div className="space-y-3">
          <div className="flex gap-2 flex-wrap">
            <ActionButton
              label="Acknowledge"
              enabled={canAck}
              variant="primary"
              loading={isActing}
              onClick={handleAck}
            />
            <ActionButton
              label="Escalate"
              enabled={canEscalate && !showResolveField}
              variant="warn"
              loading={isActing}
              onClick={handleEscalate}
            />
            <ActionButton
              label="Resolve"
              enabled={canResolve}
              variant="success"
              loading={isActing}
              onClick={handleResolveClick}
            />
          </div>

          {/* Resolve note field */}
          <AnimatePresence>
            {showResolveField && (
              <ResolveNoteField
                note={resolveNote}
                onChange={setResolveNote}
                onConfirm={handleResolveConfirm}
                onCancel={() => {
                  setShowResolveField(false);
                  setResolveNote("");
                }}
                loading={isActing}
              />
            )}
          </AnimatePresence>

          {/* Error message */}
          {error && (
            <p className="text-body-sm text-danger">{error}</p>
          )}

          <p className="text-body-sm text-tertiary">
            Actions are advisory and recorded in the audit trail. No financial action is taken automatically.
          </p>
        </div>
      )}

      {isResolved && (
        <div className="flex items-center gap-2 text-body-sm text-success">
          <CheckCircle className="size-4 shrink-0" />
          Case resolved — no further action required
        </div>
      )}

      {/* Audit timeline */}
      <AuditTimeline history={case_.history} />
    </div>
  );
}
