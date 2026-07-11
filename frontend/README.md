# ProhoriPay — Frontend

Next.js (App Router, TypeScript) frontend for the ProhoriPay decision-support
prototype. Styled with the **Blossom-Vermillion** design system (one magenta
accent, light-first), Tailwind CSS + shadcn/ui, Framer Motion, Lenis
smooth-scroll, and Recharts.

> Phase 0 scaffold: design tokens ported, providers wired, and a placeholder page
> that pings the backend `/health` endpoint. The real dashboard comes later.

## Install

```bash
cd frontend
npm install
```

## Run

```bash
npm run dev
```

Open http://localhost:3000. The home page shows a themed card with a live
**Backend connected** / **Backend unreachable** status chip and a light/dark
toggle.

## Environment

Copy `.env.local.example` to `.env.local`:

```bash
cp .env.local.example .env.local
```

| Variable | Default | Purpose |
| --- | --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | Base URL of the FastAPI backend |

The status chip turns green once the backend is running on that URL (default
`http://localhost:8000`).

## Design system

Colors, typography, and spacing come from the Blossom-Vermillion tokens in
`app/globals.css` (light + dark CSS variables) mapped to semantic Tailwind names
in `tailwind.config.ts` (`bg-brand`, `text-primary`, `bg-surface`,
`border-default`, …). **Use semantic tokens only** — never raw hex or Tailwind's
default palette. Currency/amounts use the `tabular-nums-bv` utility. See
`../shared/design.md` for the full brief.
