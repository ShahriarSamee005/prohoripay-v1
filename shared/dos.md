# Hackathon Notes: MFS Liquidity & Anomaly Detection System

> Internal implementation checklist and compliance notes for the hackathon.

---

# ✅ DO

## Data & Architecture

- ✅ Show **4 separate balance pools**:
  - Physical Cash
  - bKash
  - Nagad
  - Rocket

> **Never combine them into one total balance.**
>
> Combining balances implies interchangeability between providers, which is a compliance violation.

---

- ✅ Inject **labeled anomalies** into synthetic data from Day 1.

Reason:

- Precision
- Recall
- F1 Score

cannot be measured unless the dataset already contains known anomalies.

---

- ✅ Show provider data arriving through **separate lanes** in the architecture diagram.

**Good**

```
bKash  ─┐
         ├── Separate Processing
Nagad ──┤
         ├── Provider Isolation Layer
Rocket ─┘
```

**Bad**

One database table:

```
transactions
------------
provider
amount
...
```

This does **not** demonstrate provider isolation.

---

- ✅ Use a **weighted recent window** or trend-based burn rate.

Avoid:

```
Simple hourly average
```

Prefer:

- Exponential Moving Average (EMA)
- Weighted Moving Average
- Recent trend analysis

---

# UI & Language

Always use safe language.

Use words like:

- ✅ unusual
- ✅ requires review
- ✅ consider
- ✅ suggest
- ✅ needs attention

Avoid words like:

- ❌ suspicious
- ❌ fraud
- ❌ criminal

Language is explicitly scored.

---

- ✅ Show evidence with every anomaly.

Example:

> 12 transactions of BDT 4,950 from 3 accounts in 45 minutes.

NOT

> Risk Score: 92%

Evidence matters more than scores.

---

- ✅ Put confidence indicators beside each prediction.

Example:

```
Predicted Liquidity Shortage

Confidence:
88%
```

Not:

```
Global Status
Confidence: 88%
```

Confidence should appear where the user makes decisions.

---

- ✅ Build one connected story.

Recommended flow:

```
Liquidity Issue
      ↓
Anomaly Detected
      ↓
Alert Generated
      ↓
Assigned Officer
      ↓
Acknowledged
      ↓
Resolved
```

Avoid separate disconnected pages.

---

- ✅ Show the complete alert lifecycle.

Must include:

1. Receive
2. Assign
3. Acknowledge
4. Escalate
5. Close

Every stage should be visible in the UI.

---

# Scoring Leverage

- ✅ Include at least one alert in **Bangla** or **Banglish**.

Example:

```
⚠️ bKash balance দ্রুত কমছে।
অনুগ্রহ করে রিভিউ করুন।
```

Easy bonus points.

---

- ✅ Document these metrics inside README.

Required metrics:

- Detection Lead Time
- Precision / Recall
- API Latency

Missing these costs Data & Analytical Quality marks.

---

- ✅ Add a Responsible Design section.

Clearly state the system **will NOT**:

- Auto-freeze accounts
- Auto-transfer funds
- Label users as fraudsters

---

- ✅ Route alerts based on alert type.

Example:

| Alert | Route To |
|--------|----------|
| Liquidity | Field Officer |
| Anomaly | Risk Reviewer |
| Escalation | Supervisor |

---

# ❌ DON'T

## Hard Disqualifiers

- ❌ Never connect to real bKash, Nagad or Rocket APIs.

Use **synthetic data only**.

---

- ❌ Never use the word **fraud**.

Avoid:

- fraud
- suspicious account
- blocking
- criminal

Use:

- unusual
- requires review
- anomaly
- consider reviewing

---

- ❌ Never:

- Auto-freeze accounts
- Auto-block transactions
- Auto-transfer funds

Humans make every financial decision.

---

- ❌ Never ask for or store:

- PIN
- OTP
- Real credentials

Even dummy login forms can signal poor security design.

---

## Design Traps

- ❌ Don't build three main tabs:

```
Liquidity
Anomaly
Alerts
```

Instead, create one connected operational dashboard.

---

- ❌ Don't display:

```
Total Balance
BDT 3,000,000
```

Instead show:

```
Physical Cash
BDT ...

bKash
BDT ...

Nagad
BDT ...

Rocket
BDT ...
```

---

- ❌ Don't keep prediction confidence high if one provider's feed is delayed.

Confidence should decrease whenever dependent data becomes stale.

---

- ❌ Don't use a static anomaly threshold during Eid.

Instead use:

- Relative baseline
- Time-aware baseline
- Historical comparison

---

- ❌ Don't recommend actions that bypass provider approval.

Correct:

> Top up through bKash's approved channel.

Wrong:

> Transfer money immediately.

---

## Presentation & Submission

- ❌ Don't skip the architecture diagram in the README.

It is part of the scoring.

Show:

- Provider isolation
- Data flow
- Processing pipeline

---

- ❌ Don't claim anomaly detection works unless injected anomalies prove it.

Need measurable:

- Precision
- Recall

---

- ❌ Don't let one provider see another provider's raw data.

If asked:

> Can bKash see Nagad's balance?

The answer should be **No**, both architecturally and in the UI.

---

# ⚡ TIEBREAKERS

## 1. Bangla / Banglish Alerts

Example:

```
⚠️ Rocket balance দ্রুত কমছে।
রিভিউ প্রয়োজন।
```

Easy differentiator.

---

## 2. Connected Narrative

One screen:

```
Liquidity Crisis
        ↓
Evidence
        ↓
Alert
        ↓
Owner
        ↓
Resolution
```

is much stronger than three disconnected dashboards.

---

## 3. Demo Scenario D End-to-End

Show the complete lifecycle:

Receive

↓

Assign

↓

Acknowledge

↓

Escalate

↓

Close

---

## 4. Measurable Metrics

Example:

- Shortage detected **47 minutes before depletion**
- Precision **83%**
- Recall **89%**
- API Latency (P95): **210 ms**

Real numbers increase credibility.

---

## 5. Responsible Design

Explicitly state:

This system will **NOT**:

- Label users as fraudsters
- Freeze accounts
- Transfer funds
- Recommend financial actions without human review

---

## 6. Eid-aware Baselines

Instead of:

```
Static Threshold
```

Use:

```
Seasonal Baseline

↓

Festival Adjustment

↓

Relative Detection
```

---

# MFS Transaction Limits (Bangladesh, 2026)

## Standard Personal Account Limits

| Transaction Type | bKash | Nagad* | Rocket* |
|------------------|--------|---------|----------|
| Send Money (Per Transaction) | ৳50,000 | ৳50,000 | ৳50,000 |
| Send Money (Per Day) | ৳50,000 | ৳50,000 | ৳50,000 |
| Send Money (Per Month) | ৳300,000 | ৳300,000 | ৳300,000 |
| Max Send Money Transactions / Day | 100 | ~100 | ~100 |
| Max Send Money Transactions / Month | 250 | ~250 | ~250 |
| Cash In / Day | ৳50,000 | ৳50,000 | ৳50,000 |
| Cash Out / Day | ৳30,000 | ৳30,000 | ৳30,000 |
| Maximum Wallet Balance | ৳500,000 | Similar Regulatory Limit | Similar Regulatory Limit |

> *Nagad and Rocket generally follow Bangladesh Bank MFS limits, with small service-specific variations.

---

## Example (bKash)

A personal user can:

- Send up to **৳50,000** in a single transaction.
- Send up to **৳50,000** total per day.
- Perform up to **100 Send Money** transactions per day (within the daily amount limit).
- Send up to **৳300,000** per month.

---

# Temporary Restrictions

Bangladesh Bank may temporarily tighten limits during special events (e.g., elections).

Example:

| Transaction | Temporary Limit |
|-------------|-----------------|
| Per Transaction | ৳1,000 |
| Transactions / Day | 10 |
| Daily Total | ৳10,000 |

These are temporary and not the standard limits.

---

# Festival (Eid) Transaction Threshold Changes

During major festivals such as **Eid-ul-Fitr** and **Eid-ul-Adha**, Bangladesh Bank may temporarily increase certain MFS limits to support:

- Salary disbursements
- Eid bonuses
- Shopping
- Remittances
- Business payments

Typical changes:

| Transaction | Normal | Eid (Typical) |
|-------------|---------|---------------|
| Wallet Balance | Standard | Often Increased |
| Cash In | Standard | Often Increased |
| Merchant Payment | Standard | Often Increased Significantly |
| Add Money (Bank → Wallet) | Standard | Sometimes Increased |
| Send Money (P2P) | Usually Unchanged | Usually Unchanged or Slightly Increased |

---

## Why Are Limits Increased?

During Eid:

- Higher shopping activity
- Salary and bonus payments
- Family remittances
- Increased digital payment demand

To reduce congestion, Bangladesh Bank may increase limits for:

- Cash In
- Merchant Payments
- Add Money
- Wallet Balance

---

## Send Money During Eid

Person-to-person (P2P) **Send Money** limits are usually **not increased significantly** because regulators closely monitor them for misuse and money laundering.

In some special situations (e.g., elections), these limits may even be temporarily reduced.

---

## Example Eid Adjustment

Normal:

- Cash In: ৳50,000/day
- Merchant Payment: ৳50,000/day
- Send Money: ৳50,000/day

Possible Eid Adjustment:

- ✅ Cash In → ৳100,000/day
- ✅ Merchant Payment → ৳200,000/day
- ✅ Wallet Balance → Increased
- ➖ Send Money → Usually remains at ৳50,000/day (or only a small increase)

The exact figures vary each year based on Bangladesh Bank circulars.

---

# Key Takeaway

- Standard limits apply throughout the year.
- Bangladesh Bank may temporarily increase limits during major festivals, mainly for **Cash In**, **Merchant Payments**, **Add Money**, and **Wallet Balance**.
- **P2P Send Money limits are usually unchanged or only slightly adjusted.**
- Temporary restrictions may also be imposed during exceptional events such as elections.