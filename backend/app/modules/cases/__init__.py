"""Case-coordination module (contract Phase 4).

Auto-creates and routes a case per alert, supports guarded human transitions
(ack / escalate / resolve), and keeps an immutable, actor-attributed audit trail.
Advisory only — nothing here executes, blocks, freezes, or transfers anything.
"""
