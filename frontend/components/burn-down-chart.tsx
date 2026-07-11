"use client";

import {
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import type { Forecast } from "@/lib/types";

type ChartPoint = {
  ts: string;
  balance: number | null;
  projection: number | null;
};

function fmtTime(ts: string): string {
  const d = new Date(ts);
  const h = d.getUTCHours().toString().padStart(2, "0");
  const m = d.getUTCMinutes().toString().padStart(2, "0");
  return `${h}:${m}`;
}

function fmtBalance(v: number): string {
  return "৳" + v.toLocaleString("en-BD");
}

const TICK_STYLE = {
  fontSize: 11,
  fill: "var(--bv-text-tertiary)",
  fontVariant: "tabular-nums",
} as const;

export function BurnDownChart({ forecast }: { forecast: Forecast }) {
  const { history, projected_depletion_ts, safety_floor, trend } = forecast;
  const isGrowing = trend === "filling";

  // Build merged dataset: history points carry `balance`; the last point and the
  // projected endpoint also carry `projection` for the dashed line.
  const data: ChartPoint[] = history.map((p, i) => ({
    ts: p.ts,
    balance: p.balance,
    projection:
      i === history.length - 1 && !isGrowing && projected_depletion_ts
        ? p.balance
        : null,
  }));

  if (!isGrowing && projected_depletion_ts) {
    data.push({
      ts: projected_depletion_ts,
      balance: null,
      projection: safety_floor,
    });
  }

  // X-axis: show first, middle, last ticks only to avoid crowding
  const tickIndices = new Set([0, Math.floor(data.length / 2), data.length - 1]);
  const ticks = data
    .map((p, i) => (tickIndices.has(i) ? p.ts : null))
    .filter(Boolean) as string[];

  return (
    <div>
      <p
        className="text-label-sm text-secondary mb-2"
        style={{ fontVariant: "tabular-nums" }}
      >
        Balance history &amp; projection
      </p>
      <ResponsiveContainer width="100%" height={180}>
        <ComposedChart
          data={data}
          margin={{ top: 8, right: 8, bottom: 4, left: 4 }}
        >
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="var(--bv-border)"
            vertical={false}
          />
          <XAxis
            dataKey="ts"
            ticks={ticks}
            tickFormatter={fmtTime}
            tick={TICK_STYLE}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tickFormatter={fmtBalance}
            tick={TICK_STYLE}
            axisLine={false}
            tickLine={false}
            width={76}
            tickCount={4}
          />
          <Tooltip
            formatter={(value, name) => [
              typeof value === "number" ? fmtBalance(value) : String(value),
              name === "balance" ? "Balance" : "Projected",
            ]}
            labelFormatter={(label) =>
              typeof label === "string" ? `Time ${fmtTime(label)}` : ""
            }
            contentStyle={{
              backgroundColor: "var(--bv-surface)",
              border: "1px solid var(--bv-border)",
              borderRadius: "10px",
              fontSize: 12,
              fontVariant: "tabular-nums",
            }}
            cursor={{ stroke: "var(--bv-border)", strokeWidth: 1 }}
          />
          {/* Safety floor reference line */}
          <ReferenceLine
            y={safety_floor}
            stroke="var(--bv-warning)"
            strokeDasharray="4 2"
            label={{
              value: `Floor ${fmtBalance(safety_floor)}`,
              position: "insideTopRight",
              fontSize: 10,
              fill: "var(--bv-warning)",
            }}
          />
          {/* History — solid brand line */}
          <Line
            type="monotone"
            dataKey="balance"
            stroke="var(--bv-brand)"
            strokeWidth={2}
            dot={false}
            connectNulls={false}
          />
          {/* Projection — dashed danger line (omitted when filling) */}
          {!isGrowing && projected_depletion_ts && (
            <Line
              type="monotone"
              dataKey="projection"
              stroke="var(--bv-danger)"
              strokeWidth={2}
              strokeDasharray="6 3"
              dot={false}
              connectNulls={false}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
