# Innovation Opportunities — Implementation Spec

> **Purpose:** Feature specification for the *Super Agent Liquidity & Risk Intelligence Platform*.
> Each opportunity below is written as: what it means, a concrete example, and **what to build**.
> Use this as a reference when implementing features. All data is synthetic. The system is
> advisory only — it never executes financial transactions, never declares fraud, and always
> supports human review.

---

## Guiding Principles (apply to every feature)

- **Advisory, not authoritative** — surface signals and recommendations; humans decide.
- **Never say "fraud"** — use "unusual", "requires review", "flagged for attention".
- **Provider separation** — bKash, Nagad, Rocket are logically separate. Never imply one controls another's balance or auto-converts between them.
- **Explainability first** — every high-impact alert must expose its reason, evidence, and uncertainty.
- **Synthetic data only** — no real credentials, identities, PINs, OTPs, or account data.

---

## 1. Provider-Aware Liquidity Planning

**What it means:** Track each provider's balance (cash / e-money) separately and predict when any single provider will run low — before it happens.

**Example:**
An agent holds:
- bKash: ৳300,000
- Nagad: ৳80,000
- Rocket: ৳20,000

Each provider has its own card on the dashboard. Based on recent transaction velocity, the system predicts **Rocket will run out by ~3 PM** due to expected cash-out demand.

**What to build:**
- A dashboard with **one card per provider** showing current balance + a health indicator.
- A **forecast engine** that projects time-to-depletion per provider from recent transaction data.
- A **pre-shortage warning** shown on the provider card *before* depletion.
- On entering a provider's detail view: full shortage breakdown, **estimated depletion timeframe**, and a **top-up recommendation**.

**Data inputs:** per-provider current balance, recent transaction rate (cash-out velocity), historical patterns.
**Output:** `{ provider, current_balance, projected_depletion_time, confidence, recommended_action }`

---

## 2. Cross-Provider Operational Context

**What it means:** Don't analyze providers in isolation. Read all providers together to understand the real cause of a change.

**Example:**
- bKash transactions suddenly **drop**.
- Nagad transactions suddenly **rise**.

Instead of flagging "bKash has a problem," the system infers: *customers are switching from bKash to Nagad because bKash is temporarily slow*, and warns about **incoming load on Nagad**.

**What to build:**
- A **correlation layer** that compares transaction trends across providers simultaneously.
- Logic to detect **compensating shifts** (one provider down + another up = migration, not failure).
- A forward alert about the **provider gaining traffic** so its liquidity can be prepared.

**Data inputs:** synchronized transaction streams from all providers.
**Output:** contextual insight, e.g. `"Traffic shifting bKash → Nagad; prepare Nagad liquidity."`

---

## 3. Explainable Anomaly & Risk Evidence

**What it means:** Never show a bare risk score. Always explain **why** something was flagged.

**Example:**

❌ Bad: `Risk Score = 92`

✅ Good:
- 15 transfers in 3 minutes
- Far above this user's normal behavior
- New device
- New location
- Amount 5× larger than usual

Now the operator understands the reasoning.

**What to build:**
- Every alert carries an **evidence list** (the specific signals that triggered it).
- Display **baseline vs observed** comparisons ("normal: 2/min → observed: 15/min").
- Attach an **uncertainty/confidence** value to each alert.
- **Never** present a score alone as justification.

**Output schema:**
```json
{
  "alert_id": "...",
  "label": "unusual — requires review",
  "evidence": ["15 transfers in 3 min", "5× typical amount", "new device"],
  "baseline": {...},
  "observed": {...},
  "confidence": 0.0-1.0
}
```

---

## 4. Human Review & Feedback Loops

**What it means:** Humans can approve or reject the system's flags, and the system incorporates that feedback.

**Example:**
- System: *"Possible unusual activity."*
- Officer reviews manually: *"This is actually a salary payment."*
- System stores the feedback → similar transactions are **less likely to be flagged** next time.

**What to build:**
- A **review action** on each alert: `Confirm` / `Dismiss` / `Escalate`, with an optional note.
- **Persist feedback** linked to the alert and its features.
- Feed confirmed/dismissed labels back into detection thresholds or a learning component.
- Record who reviewed, when, and the outcome (for auditability — see #9).

**Output:** feedback record `{ alert_id, reviewer, decision, reason, timestamp }`.

---

## 5. Provider-Aware Alert Ownership, Escalation & Resolution

**What it means:** Each provider gets alerts for **its own system only**, and unresolved issues **escalate automatically** up the hierarchy.

**Example — a Rocket API failure:**
- Rocket support team is notified (not everyone).
- Not fixed in **30 min** → Supervisor notified.
- Not fixed in **1 hour** → Regional manager notified.

This prevents notification confusion.

**What to build:**
- **Alert routing** by provider — each provider sees only its relevant alerts.
- A **case lifecycle:** `raised → routed → acknowledged → resolved / escalated`.
- **Time-based auto-escalation** rules (e.g., 30 min → supervisor, 1 hr → regional manager).
- Each alert shows: **who receives it, who owns it, recommended next step, current status.**

**Escalation ladder (configurable):** `agent/outlet → field officer → area manager → central ops`.
**Output:** case object `{ id, provider, owner, status, escalation_level, next_step, history[] }`.

---

## 6. Context-Aware Distinction: Legitimate Spikes vs Suspicious Patterns

**What it means:** A traffic surge isn't automatically suspicious. Understand **why** volume rose.

**Example 1 — Legitimate:**
Eid shopping. Normal: 500 txns/hr → Today: 2,500 txns/hr.
System checks date/known events, recognizes **Eid**, treats it as **normal demand**.

**Example 2 — Suspicious:**
Tuesday, 3 AM. Normal: 20 txns/hr → Suddenly: 2,500 txns/hr.
No festival, no salary day, no campaign → **flagged for review**.

**What to build:**
- A **context calendar** of known events (Eid, salary days, campaigns, local events).
- Spike detection that **cross-references context** before flagging.
- Classify surges as **expected demand** vs **requires review**, with the reasoning attached.

**Data inputs:** transaction volume, timestamp, known-event calendar, historical baselines.
**Output:** `{ spike_detected: true, classification: "expected | review", reason: "..." }`

---

## 7. Inclusive Agent-Side Communication

**What it means:** Communicate so **any** agent understands, regardless of language or technical skill.

**Example:**

❌ Technical: `Liquidity imbalance detected.`

✅ Human: `⚠️ Your Nagad balance is low. Please add more balance before customers arrive.`

Even better: **Bangla language**, voice alerts, simple icons.

**What to build:**
- Alerts in **plain Bangla / Banglish / English** (selectable per user).
- **Icons and color-coded status** for at-a-glance clarity.
- Optional **voice alert** for critical warnings.
- Keep messages **action-oriented** ("add balance now") rather than abstract.

**Output example (Bangla):**
`⚠️ আপনার নগদ ব্যালেন্স কমে যাচ্ছে। গ্রাহক আসার আগে ব্যালেন্স যোগ করুন।`

---

## 8. Privacy-Preserving Synthetic Data Design

**What it means:** Use realistic but **fake** data — protect privacy while keeping patterns testable.

**Example:**

❌ Real: `Name: Rifat Ahmed | Phone: 01712345678 | Amount: ৳18,500`

✅ Synthetic: `Name: User_1034 | Phone: 01700000001 | Amount: ৳18,720`

Patterns stay realistic; no real customer is exposed.

**What to build:**
- A **synthetic data generator** producing agents, providers, transactions, balances, event flags, case status.
- **Anonymized identifiers** only (`User_1034`, `Agent_07`, `01700000001`).
- Realistic **distributions and patterns** (amounts, timing, velocity) so analytics are meaningful.
- **Injectable known anomalies** so detection can be measured (precision / recall / false-positive rate).
- A **data & simulation note** documenting how data was made, assumptions, and limitations.

**Fields:** `agent_id, provider_id, area, timestamp, txn_type, amount, status, opening_balance, current_balance, event_flag, case_status`.

---

## 9. Scalable Monitoring & Traceability

**What it means:** Keep working as volume grows, and record **exactly what happened** at every step.

**Example:**
- Today: 100 agents, 20,000 transactions.
- Next year: 50,000 agents, 100M transactions/day.

The system should still monitor smoothly. Every alert must be **traceable** end to end:

```
Transaction Created
    ↓
Risk Score Generated
    ↓
Alert Sent
    ↓
Officer Reviewed
    ↓
Case Closed
```

**What to build:**
- An **audit trail** logging each stage of an alert's lifecycle with timestamps.
- **Traceability** from raw transaction → signal → alert → review → resolution.
- Architecture that **degrades gracefully** and stays responsive under demonstrated data volume.
- Metrics/logs during **delayed, missing, or inconsistent** provider input (prove safe fallback).

**Output:** immutable event log per case `{ stage, actor, timestamp, detail }`.

---

## Implementation Priority (suggested)

| Priority | Feature | Why |
|----------|---------|-----|
| **Must-have** | #1 Liquidity planning | Core mandatory capability (shortage + timing) |
| **Must-have** | #3 Explainable evidence | Mandatory: alerts must show reason + uncertainty |
| **Must-have** | #5 Ownership & escalation | Mandatory: ≥1 alert with routing/owner/next-step/status |
| **Must-have** | #8 Synthetic data | Foundation for everything + required data note |
| **High** | #6 Context-aware spikes | Distinguishes demand vs review (mandatory-adjacent) |
| **High** | #9 Traceability | Required audit trail + ≥3 measurable metrics |
| **Medium** | #7 Inclusive Bangla comms | Strong, cheap UX/explainability points |
| **Medium** | #4 Feedback loops | Responsible-design differentiator |
| **Stretch** | #2 Cross-provider context | High-innovation, do after core is solid |

---

## Hard Guardrails (do not violate)

- ❌ No real wallets, accounts, credentials, PINs, OTPs, passwords.
- ❌ No auto-blocking, freezing, accusing, or final fraud determination.
- ❌ No implied conversion/transfer between provider balances.
- ✅ All risk signals advisory; all high-impact actions gated behind human review.
- ✅ Document assumptions, synthetic patterns, limitations, and expected false positives.
