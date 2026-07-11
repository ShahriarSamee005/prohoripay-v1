# Main Prompt to Generate the Master Prompt

You are a hackathon expert with **10+ years of winning experience**. Help me regarding the **hackathon main round today**.

## Core Instructions

* **Ask me before giving any code.**
* Ask me if you need to know anything or if you are confused about anything.
* Stick strictly to the provided PDF instructions.
* Ensure we fulfill **every evaluation criterion and requirement**.
* Use a **modular pattern** in the backend.
* Develop the project in **modules**.
* Finish all required features.
* Run tests throughout development.
* We will be building using **Claude Code**.

Generate the prompts in an order that ensures proper continuation and synchronization between the **frontend and backend**, so both are always working on the **same feature**.

Divide development into phases where appropriate.

Explain how I should use the prompts to get the most efficient results.

Every phase should include:

* Clear scope
* Frontend tasks
* Backend tasks
* Integration requirements
* Testing
* Checkpoints
* A strict stop condition before moving to the next phase

---

# Project

## Project Name

**ProhoriPay**

## Tech Stack

### Frontend

* Next.js
* Framer Motion
* Lenis
* shadcn/ui
* Recharts
* Leaflet, if we implement the hotspot map

### Backend

* FastAPI (Python)

### Analytics

* pandas
* numpy
* scikit-learn

### Data

* Faker
* numpy
* SQLite
* SQLModel / SQLAlchemy

### Live Flow

* Simulation clock
* Server-Sent Events (SSE)

### LLM

* Groq API

---

# UI Requirements

The dashboard should contain a prominent **main card** displaying the agent's **total available money**.

Underneath the total amount, show a breakdown of:

* Physical cash
* Balance available across all providers

Each provider should display:

* Provider logo
* Available amount

Below the main balance section, create a **single-row card section** containing one card for each provider.

Each provider card should redirect to that provider's dedicated screen.

The provider details screen should include information such as:

* Current available balance
* Remaining liquidity
* Active warnings
* Predicted future liquidity requirements
* Estimated depletion time
* Recent transaction behavior
* Relevant anomalies
* Operational recommendations

Additional UI elements can be designed as needed and refined later.

---

# Liquidity Prediction and AI

## How Liquidity Prediction Works

Our platform predicts liquidity using **deterministic analytics**, not a Large Language Model (LLM).

The prediction engine continuously analyzes:

* Current shared cash available
* Current balance for each provider
* Recent transaction history
* Cash-in and cash-out rates
* Net cash flow
* Transaction velocity
* Historical trends over a configurable time window

Using these inputs, the system calculates:

* Current consumption rate
* Average withdrawal rate
* Provider-specific depletion rate
* Estimated remaining operational time before liquidity becomes insufficient
* Overall confidence of the prediction

### Example

If an agent currently has **৳20,000** in their bKash balance and the recent average cash-out rate is **৳2,000 per minute**, the system estimates that the balance may be exhausted in approximately **10 minutes**, assuming current conditions continue.

These calculations must be:

* Transparent
* Reproducible
* Explainable
* Easy for operations teams to understand

---

# Why We Don't Use AI for Prediction

We intentionally do **not** use an LLM to calculate liquidity forecasts.

Operational decisions should be based on measurable data and deterministic calculations, ensuring that every prediction can be explained and verified.

Using mathematical forecasting instead of generative AI provides:

* Consistent results
* Explainable calculations
* Better reliability
* Easier validation
* Higher trust for operational decision-making

This aligns with the hackathon's emphasis on **evidence-based decision support** rather than opaque AI-generated decisions.

---

# How AI (Groq) Is Used

Instead of performing calculations, the **Groq LLM** acts as an **AI Operations Assistant**.

Once the analytics engine has completed all calculations, it sends the structured results to the LLM.

The AI then transforms technical outputs into clear, human-readable explanations.

### Example Structured Output

```text
Provider: bKash
Balance: ৳20,000
Cash-out Rate: ৳2,000/min
Predicted Shortage: 10 minutes
Confidence: 92%
```

### Example AI Explanation

> The bKash balance has been decreasing steadily over the past hour due to sustained cash-out activity. Based on the current transaction rate, the provider balance may become insufficient within approximately 10 minutes. Consider replenishing the provider balance or redirecting customers to another nearby agent. Human review is recommended.

This makes the dashboard easier for operators to understand without requiring them to interpret raw metrics.

---

# AI Responsibilities

The LLM is responsible for:

* Explaining liquidity predictions in natural language
* Summarizing detected anomalies
* Providing contextual operational recommendations
* Explaining confidence levels
* Generating concise alert summaries
* Producing multilingual responses:

  * English
  * Bangla
  * Banglish

## The AI Does Not

The AI must **not**:

* Calculate liquidity forecasts
* Detect anomalies independently
* Make financial decisions
* Label transactions as fraud
* Automatically approve or reject actions

---

# Overall Workflow

```text
Synthetic Transaction Data
            │
            ▼
 Analytics Engine (Python)
            │
            ├── Liquidity Forecast
            ├── Anomaly Detection
            ├── Confidence Score
            └── Supporting Evidence
                    │
                    ▼
               Groq LLM
                    │
                    ▼
 Converts technical results into
 natural-language explanations
                    │
                    ▼
          Next.js Dashboard
```

---

# One-Sentence Summary

**The analytics engine determines what is happening using transparent calculations, while the AI explains why it is happening and recommends appropriate next steps in language that is easy for human operators to understand.**

This division of responsibility is robust, explainable, and well aligned with the hackathon's focus on **safe, human-centered decision support**.

---

# Required Reference Files

You have access to the following project files:

* `Dos.md`

  * Do's and don'ts
  * Tie-breakers
  * Constraints

* Other catches, constraints, and do's and don'ts available in the chat context

* `design.md`

  * Use **only the design system and visual direction** from this file.
  * Use the **tech stack specified in this prompt**, even if the file mentions another stack.

* `our_idea.md`

  * Contains our innovation and project concept.

You must read and follow these files before planning or implementing relevant features.

Create synthetic mock data and anomaly scenarios according to the official problem statement and project requirements.

---

# Phase 0 — Foundation

## Backend Prompt

Read `./CLAUDE.md` and `./shared/contract.md` fully before doing anything.

Work **ONLY** inside:

```text
./backend
```

## Phase 0 Goal

Build a modular FastAPI skeleton that:

* Runs successfully
* Connects to SQLite
* Serves `GET /health`
* Has a passing pytest harness

**Do NOT build any feature endpoints beyond `/health` yet.**

## Build in `./backend`

### Dependencies

Create either:

```text
pyproject.toml
```

or:

```text
requirements.txt
```

Include:

* fastapi
* uvicorn[standard]
* sqlmodel
* pydantic-settings
* pytest
* httpx
* python-dotenv
* pandas
* numpy
* scikit-learn
* faker

Add the analytics and synthetic-data dependencies now so later phases require no reinstall, but **do not use them yet**.

### Modular Layout

```text
backend/
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py
│   │   └── db.py
│   └── modules/
│       └── health/
│           └── router.py
├── tests/
│   └── test_health.py
├── .env.example
└── README.md
```

### File Responsibilities

#### `app/main.py`

Keep this file thin.

It should contain only:

* FastAPI app creation
* CORS configuration
* Module router inclusion
* Application startup wiring where necessary

**Do not place business logic in `main.py`.**

#### `app/core/config.py`

Use `pydantic-settings`.

Read configuration from `.env`, including:

* `GROQ_API_KEY`
* Database URL
* CORS origins

#### `app/core/db.py`

Implement:

* SQLModel engine
* `get_session` dependency
* `init_db()`

#### `app/modules/health/router.py`

Implement:

```http
GET /health
```

Response:

```json
{
  "status": "ok",
  "time": "ISO-8601 UTC timestamp"
}
```

#### `tests/test_health.py`

Test that:

* The endpoint returns HTTP `200`
* `status == "ok"`

### CORS

Allow:

```text
http://localhost:3000
```

### `.env.example`

```env
GROQ_API_KEY=
DATABASE_URL=sqlite:///./prohoripay.db
CORS_ORIGINS=http://localhost:3000
```

### `backend/README.md`

Include short instructions for:

* Installation
* Running the backend
* Running tests

Run command:

```bash
uvicorn app.main:app --reload
```

Test command:

```bash
pytest
```

## Backend Architecture Rule

Each feature module must be self-contained and may contain:

* Router
* Schemas
* Models
* Services
* Analytics logic
* Tests

Do not place business logic in `main.py`.

## Backend Test Gate

The following must pass before stopping:

1. `pytest` is green.
2. `uvicorn app.main:app --reload` starts with no errors.
3. `GET /health` returns HTTP `200`.
4. The response contains:

```json
{
  "status": "ok"
}
```

Run the tests and server verification.

Paste the relevant output.

Then **STOP**.

**Do not start Phase 1.**

---

# Phase 0 — Frontend

## Frontend Prompt

Read the following files fully before doing anything:

```text
./CLAUDE.md
./shared/contract.md
./shared/design.md
```

Work **ONLY** inside:

```text
./frontend
```

## Phase 0 Goal

Create a Next.js application with:

* The Blossom-Vermillion design system
* shadcn/ui
* Framer Motion
* Lenis
* Recharts
* Backend health-check integration

Create only a placeholder page that fetches the backend `/health` endpoint and renders its status using themed components.

**Do NOT build the real dashboard yet.**

## Build in `./frontend`

### Next.js

Use:

* Next.js
* App Router
* TypeScript
* Tailwind CSS

Scaffold using `create-next-app`.

### Blossom-Vermillion Design System

Port the tokens from:

```text
./shared/design.md
```

into:

```text
app/globals.css
```

Use CSS variables for both:

* Light theme
* Dark theme

Use **exactly the token table defined in `design.md`**.

Map the tokens in:

```text
tailwind.config.ts
```

using the same semantic naming system, including examples such as:

* `bg-brand`
* `text-primary`
* `bg-surface`
* `border-default`

### Design Rules

* Add the `tabular-nums-bv` utility.
* Use the Inter font.
* Magenta `#E3106D` is the **only accent color**.
* Do not introduce a second accent color.
* Use semantic tokens only.
* Do not use raw hex values in components.
* Do not use the default Tailwind color palette.
* All numbers must use `tabular-nums-bv`.

### shadcn/ui

Initialize shadcn/ui.

Theme it using the Blossom-Vermillion tokens.

Set:

```text
primary = brand magenta
```

### Theme Provider

Create a `ThemeProvider` with:

* Light theme as default
* Light/dark theme toggle
* Theme applied using `class` and `data-theme` on `<html>`
* Theme persisted to:

```text
localStorage
```

using the key:

```text
bv-theme
```

### Additional Libraries

Install and configure:

* Framer Motion
* Lenis
* Recharts

Create a smooth-scroll provider using Lenis and wrap the application with it.

Recharts only needs to be installed in this phase. **Do not use it yet.**

### API Client

Create:

```text
lib/api.ts
```

The client should:

* Read `NEXT_PUBLIC_API_BASE_URL`
* Provide a typed `getHealth()` function
* Include TypeScript types matching `contract.md`

Include types for:

* `Agent`
* `Pool`
* `Transaction`

These may remain unused during Phase 0.

### Placeholder Home Page

Create a themed `Card` following the recipe in `design.md`.

The page should:

1. Call `getHealth()`.
2. Display a green status chip when successful:

```text
Backend connected
```

3. Display a danger status chip when the connection fails.
4. Include a light/dark theme toggle.

This page should prove:

* The design tokens work.
* The theme system works.
* The frontend can communicate with the backend.

### `.env.local.example`

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

### `frontend/README.md`

Include short instructions for:

* Installation
* Running the frontend
* Environment configuration

Run command:

```bash
npm run dev
```

## Frontend Test Gate

The following must pass before stopping:

1. `npm run dev` runs without errors.
2. The page renders with the magenta accent visible.
3. With the backend running on port `8000`, the status chip displays:

```text
Backend connected
```

4. The light/dark toggle changes the theme correctly.
5. Design tokens re-resolve correctly after switching themes.

Confirm all five checks.

Paste any errors encountered and explain how they were resolved.

Then **STOP**.

**Do not start Phase 1.**
