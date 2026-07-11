import type { PoolStatus } from "@/lib/types";

const STATUS_CONFIG: Record<
  PoolStatus,
  { label: string; icon: string; classes: string }
> = {
  healthy: {
    label: "Healthy",
    icon: "✓",
    classes: "bg-surface-high text-success border-default",
  },
  watch: {
    label: "Needs attention",
    icon: "●",
    classes: "bg-surface-high text-warning border-default",
  },
  critical: {
    label: "Critical",
    icon: "⚠",
    classes:
      "border border-danger bg-surface-high text-danger",
  },
};

export function PoolStatusChip({ status }: { status: PoolStatus }) {
  const cfg = STATUS_CONFIG[status];
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-pill border px-2.5 py-0.5 text-label-sm ${cfg.classes}`}
    >
      <span aria-hidden>{cfg.icon}</span>
      {cfg.label}
    </span>
  );
}
