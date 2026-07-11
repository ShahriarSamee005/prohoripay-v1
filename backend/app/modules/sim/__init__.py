"""Simulation module (contract Phase 5).

A deterministic simulation clock advances synthetic time in ticks, applies
direction-aware transactions, re-runs forecast + detection + escalation each tick,
and streams the changes over SSE. Presenter-driven controls (start/pause/reset,
eid_rush, inject_anomaly, break_feed/restore_feed) drive live scenarios.

Still advisory only — every control generates SYNTHETIC events; nothing here
executes, blocks, freezes, or transfers a real financial action.
"""
