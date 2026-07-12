"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Pencil, Check, X as XIcon, Plus, Minus } from "lucide-react";
import type { Pool, Forecast, PoolStatus } from "@/lib/types";
import { patchPhysicalCash } from "@/lib/api";

interface HeroCardProps {
  pools: Pool[];
  forecasts?: Forecast[];
  agentName: string;
  agentArea: string;
  onBalancePatched?: (newBalance: number) => void;
}

function fmt(n: number) {
  return n.toLocaleString("en-BD");
}

function StatusBadge({ status }: { status: PoolStatus }) {
  const cfg =
    status === "critical"
      ? { label: "Critical", dot: "rgba(255,110,100,1)", bg: "rgba(255,80,70,0.18)", border: "rgba(255,100,90,0.35)" }
      : status === "watch"
        ? { label: "Needs attention", dot: "rgba(255,210,90,1)", bg: "rgba(255,195,60,0.18)", border: "rgba(255,200,80,0.35)" }
        : { label: "Healthy", dot: "rgba(120,230,150,1)", bg: "rgba(80,210,120,0.18)", border: "rgba(100,220,130,0.35)" };

  return (
    <span
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-pill text-label-sm font-semibold"
      style={{ background: cfg.bg, border: `1px solid ${cfg.border}`, color: "rgba(255,255,255,0.92)" }}
    >
      <span className="size-1.5 rounded-full shrink-0" style={{ backgroundColor: cfg.dot }} />
      {cfg.label}
    </span>
  );
}

export function HeroCard({
  pools,
  forecasts,
  agentName,
  agentArea,
  onBalancePatched,
}: HeroCardProps) {
  const physical = pools.find((p) => p.kind === "physical_cash");

  const cashForecast = forecasts?.find(
    (f) => f.pool_id === physical?.pool_id
  );
  const depletionMins =
    cashForecast?.projection_state === "projected"
      ? cashForecast.minutes_to_depletion
      : null;

  // ── Edit state ───────────────────────────────────────────────────────────────
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  function startEdit() {
    setDraft(String(physical?.balance ?? 0));
    setSaveError(null);
    setEditing(true);
  }

  useEffect(() => {
    if (editing) inputRef.current?.select();
  }, [editing]);

  function cancelEdit() {
    setEditing(false);
    setSaveError(null);
  }

  async function confirmEdit() {
    const parsed = parseInt(draft.replace(/[^0-9]/g, ""), 10);
    if (isNaN(parsed) || parsed < 0) {
      setSaveError("Enter a valid amount (≥ 0)");
      return;
    }
    setSaving(true);
    setSaveError(null);
    try {
      const res = await patchPhysicalCash({
        balance: parsed,
        note: "Manual cash count",
      });
      if (res.ok) {
        onBalancePatched?.(res.balance);
        setEditing(false);
      }
    } catch {
      setSaveError("Could not save. Try again.");
    } finally {
      setSaving(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") confirmEdit();
    if (e.key === "Escape") cancelEdit();
  }

  if (!physical) return null;

  return (
    <motion.div
      className="relative overflow-hidden rounded-xl shadow-brand-glow"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      style={{
        background:
          "linear-gradient(135deg, var(--bv-brand-bright) 0%, var(--bv-brand-deep) 100%)",
      }}
    >
      {/* Grid texture */}
      <div
        className="absolute inset-0 opacity-10 pointer-events-none"
        style={{
          backgroundImage:
            "repeating-linear-gradient(0deg,transparent,transparent 23px,rgba(255,255,255,.15) 23px,rgba(255,255,255,.15) 24px)," +
            "repeating-linear-gradient(90deg,transparent,transparent 23px,rgba(255,255,255,.15) 23px,rgba(255,255,255,.15) 24px)",
        }}
      />

      <div className="relative z-10 p-5 flex flex-col gap-4 text-on-brand">
        {/* Agent identity + depletion chip */}
        <div className="flex items-start justify-between gap-2">
          <div>
            <p className="text-label-md opacity-75">Agent</p>
            <p className="text-title-lg">{agentName}</p>
            <p className="text-body-sm opacity-70">{agentArea}</p>
          </div>
          {depletionMins != null && (
            <motion.span
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              className="shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-pill text-label-sm font-semibold"
              style={{
                backgroundColor: "rgba(255,255,255,0.22)",
                backdropFilter: "blur(8px)",
              }}
            >
              <span className="size-1.5 rounded-full bg-white animate-pulse" />
              ~{depletionMins} min
            </motion.span>
          )}
        </div>

        {/* Physical cash balance — editable */}
        <div>
          <div className="flex items-center gap-2 mb-0.5">
            <p className="text-label-md opacity-75">Physical Cash Drawer</p>
            {!editing && (
              <button
                onClick={startEdit}
                aria-label="Edit cash drawer amount"
                className="flex items-center justify-center size-6 rounded-md transition-all duration-fast active:scale-90"
                style={{ background: "rgba(255,255,255,0.18)", color: "rgba(255,255,255,0.85)" }}
              >
                <Pencil className="size-3" />
              </button>
            )}
          </div>

          <AnimatePresence mode="wait">
            {editing ? (
              <motion.div
                key="edit"
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 4 }}
                transition={{ duration: 0.15 }}
                className="flex flex-col gap-2"
              >
                {/* Stepper row: −100 · input · +100 */}
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => {
                      const v = Math.max(0, parseInt(draft || "0", 10) - 100);
                      setDraft(String(v));
                      setSaveError(null);
                    }}
                    disabled={saving}
                    aria-label="Decrease by 100"
                    className="flex items-center justify-center size-9 rounded-xl shrink-0 transition-all duration-fast active:scale-90 disabled:opacity-40"
                    style={{ background: "rgba(255,255,255,0.18)", color: "rgba(255,255,255,0.9)" }}
                  >
                    <Minus className="size-4" />
                  </button>

                  <div
                    className="flex items-center gap-2 flex-1 rounded-xl px-3 py-2"
                    style={{
                      background: "rgba(255,255,255,0.15)",
                      backdropFilter: "blur(8px)",
                      border: "1.5px solid rgba(255,255,255,0.35)",
                    }}
                  >
                    <span className="text-display-sm font-bold tabular-nums-bv leading-none" style={{ color: "rgba(255,255,255,0.65)" }}>
                      ৳
                    </span>
                    <input
                      ref={inputRef}
                      type="number"
                      min={0}
                      value={draft}
                      onChange={(e) => { setDraft(e.target.value); setSaveError(null); }}
                      onKeyDown={handleKeyDown}
                      className="flex-1 bg-transparent text-display-sm tabular-nums-bv font-bold leading-none outline-none w-0 min-w-0"
                      style={{ color: "rgba(255,255,255,0.98)" }}
                      aria-label="New physical cash balance"
                      inputMode="numeric"
                    />
                  </div>

                  <button
                    onClick={() => {
                      const v = parseInt(draft || "0", 10) + 100;
                      setDraft(String(v));
                      setSaveError(null);
                    }}
                    disabled={saving}
                    aria-label="Increase by 100"
                    className="flex items-center justify-center size-9 rounded-xl shrink-0 transition-all duration-fast active:scale-90 disabled:opacity-40"
                    style={{ background: "rgba(255,255,255,0.18)", color: "rgba(255,255,255,0.9)" }}
                  >
                    <Plus className="size-4" />
                  </button>
                </div>

                <p className="text-label-sm opacity-60 px-1">±100 BDT per tap · or type any amount</p>

                {saveError && (
                  <p className="text-label-sm px-1" style={{ color: "rgba(255,160,140,1)" }}>
                    {saveError}
                  </p>
                )}

                <div className="flex items-center gap-2">
                  <button
                    onClick={confirmEdit}
                    disabled={saving}
                    className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-label-md font-semibold transition-all duration-fast disabled:opacity-50 active:scale-95"
                    style={{ background: "rgba(255,255,255,0.92)", color: "var(--bv-brand-deep)" }}
                  >
                    {saving ? (
                      <span className="size-3.5 rounded-full border-2 border-current border-t-transparent animate-spin" />
                    ) : (
                      <Check className="size-3.5" />
                    )}
                    Save
                  </button>
                  <button
                    onClick={cancelEdit}
                    disabled={saving}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-label-md transition-all duration-fast active:scale-95"
                    style={{ background: "rgba(255,255,255,0.15)", color: "rgba(255,255,255,0.85)" }}
                  >
                    <XIcon className="size-3.5" />
                    Cancel
                  </button>
                </div>
              </motion.div>
            ) : (
              <motion.div
                key="display"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.15 }}
                className="flex flex-col gap-2"
              >
                <p className="text-display-lg tabular-nums-bv leading-none">
                  <motion.span
                    key={physical.balance}
                    initial={{ opacity: 0.5, y: -4 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.2 }}
                  >
                    ৳{fmt(physical.balance)}
                  </motion.span>
                </p>
                <div className="flex items-center gap-2">
                  <StatusBadge status={physical.status} />
                  <p className="text-body-sm opacity-55">
                    Shared drawer · not e-money
                  </p>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </motion.div>
  );
}
