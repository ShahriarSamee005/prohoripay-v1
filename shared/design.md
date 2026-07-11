# Blossom-Vermillion — Design System

> A brief for Claude Code (and any developer) working in this repo. Read this
> before building UI. It explains what the system is, how it's wired, and the
> rules to follow so new screens stay consistent.

---

## 1. What this is

**Blossom-Vermillion** is a design system for a **crypto / finance wallet** UI.
It's a hybrid:

- **Structure** comes from a dark crypto-wallet reference (hero "wallet value"
  card, portfolio risk gauges, timeframe pills, transaction rows, circular nav).
- **Color** is a single **magenta-pink** accent — `#E3106D`. There is **no
  secondary accent** (an earlier version had gold; it was intentionally dropped).
- It is **light-first**: the default theme is light (warm-white surfaces, magenta
  accent). A **dark** variant echoes the original near-black wallet screenshot.

**One-line identity:** clean financial surfaces, one confident magenta accent,
large tabular numbers, generous rounded cards.

---

## 2. Tech stack & where things live

- **React 18 + TypeScript**, styled with **Tailwind CSS**.
- Colors are defined **once** as CSS variables and Tailwind maps onto them, so
  theming is automatic (flip one class on `<html>`, everything re-resolves).

```
src/theme/
  tokens.css        ← SOURCE OF TRUTH for color (CSS vars, light + dark)
  tokens.ts         ← same values in TS + spacing/radius/duration + getToken()
  typography.ts     ← type scale; feeds Tailwind fontSize
  ThemeProvider.tsx ← light/dark/system switching (class + data-theme on <html>)
  index.ts          ← barrel: import { ThemeProvider, useTheme, palette } from '@/theme'
tailwind.config.ts  ← maps Tailwind color/font/radius/shadow names → CSS vars
src/index.css       ← imports tokens.css + Tailwind layers + Inter
```

### Setup (once, at app entry)

```tsx
// main.tsx
import './index.css';                 // tokens + tailwind
import { ThemeProvider } from '@/theme';

createRoot(document.getElementById('root')!).render(
  <ThemeProvider defaultTheme="light">   {/* "light" | "dark" | "system" */}
    <App />
  </ThemeProvider>,
);
```

---

## 3. Color tokens — use these names, never raw hex

Every color is a Tailwind class backed by a CSS var. **Do not hardcode hex in
components.** If you need a value in JS, read it live with `getToken('--bv-brand')`
so it stays theme-aware.

| Purpose | Tailwind class | CSS var | Light | Dark |
| --- | --- | --- | --- | --- |
| Primary accent | `bg-brand` `text-brand` `border-brand` | `--bv-brand` | `#E3106D` | `#F0387F` |
| Accent (pressed/deep) | `bg-brand-deep` | `--bv-brand-deep` | `#C20E5F` | `#C20E5F` |
| Accent (bright) | `bg-brand-bright` | `--bv-brand-bright` | `#F0387F` | `#F0387F` |
| On-accent text/icon | `text-on-brand` | `--bv-on-brand` | `#FFFFFF` | `#FFFFFF` |
| App background | `bg-background` | `--bv-background` | `#FAF3F6` | `#050505` |
| Card / sheet | `bg-surface` | `--bv-surface` | `#FFFFFF` | `#111111` |
| Raised surface | `bg-surface-high` | `--bv-surface-high` | `#F3EAEE` | `#1C1C1C` |
| Magenta hero surface | `bg-surface-brand` | `--bv-surface-brand` | `#E3106D` | `#E3106D` |
| Hairline / divider | `border-default` | `--bv-border` | `rgba(0,0,0,.08)` | `rgba(255,255,255,.12)` |
| Text primary | `text-primary` | `--bv-text-primary` | `#1E1418` | `#F7F5F6` |
| Text secondary | `text-secondary` | `--bv-text-secondary` | `#645157` | `#AEA6A9` |
| Text tertiary | `text-tertiary` | `--bv-text-tertiary` | `#9A8B91` | `#6E6669` |
| Success (gains/confirmed) | `text-success` | `--bv-success` | `#3E9E5C` | `#70AF92` |
| Warning (pending) | `text-warning` | `--bv-warning` | `#C98A1E` | `#E0B25A` |
| Danger (loss/failed) | `text-danger` | `--bv-danger` | `#C5392F` | `#E05043` |
| Info | `text-info` | `--bv-info` | `#35699E` | `#6FA3D1` |

**Opacity modifiers** work on the brand token via rgb wrapping is not enabled by
default; for translucent magenta use the provided `shadow-brand-glow` or an
explicit `rgba(...)`. Keep opacity use rare.

### The hero gradient

The magenta hero card (wallet value / reward panels) uses a utility, not a color
token:

```tsx
<div className="bg-brand-gradient rounded-xl p-6 text-on-brand shadow-brand-glow">…</div>
```

`.bg-brand-gradient` = `linear-gradient(135deg, #F0387F → #C20E5F)` (theme-aware).

---

## 4. Typography — the financial scale

Font is **Inter** (`font-sans`). The scale is defined in `typography.ts` and
exposed as Tailwind text classes. Numbers are the star of a wallet UI: display
sizes are large, tight, and **use tabular figures**.

| Class | Size / weight | Use for |
| --- | --- | --- |
| `text-display-lg` | 46 / 700 | The big wallet value (`$41,812.14`) |
| `text-display-md` | 38 / 700 | Secondary big figures |
| `text-display-sm` | 30 / 700 | Percent / stat callouts |
| `text-headline-lg` … `-sm` | 26–20 / 700–600 | Screen & section titles |
| `text-title-lg` … `-sm` | 18–13 / 600 | Card headers, row labels |
| `text-body-lg` … `-sm` | 16–12 / 400 | Descriptions, meta |
| `text-label-lg` … `-sm` | 15–11 / 600 | Buttons, chips, timeframe pills, data |

**Rule:** any currency, amount, or percentage that appears in a column or updates
live gets `tabular-nums-bv` so digits don't jitter:

```tsx
<span className="text-display-lg tabular-nums-bv">$41,812.14</span>
```

---

## 5. Shape, spacing, elevation

- **Radius:** `rounded-sm` 10 · `rounded-md` 14 · `rounded-lg` 20 (cards) ·
  `rounded-xl` 28 (hero cards / sheets) · `rounded-pill` full. Cards are
  generously rounded — default to `rounded-lg`, hero elements to `rounded-xl`.
- **Spacing:** use Tailwind's default 4px scale. Token reference (from
  `tokens.ts`): xs 8 · sm 12 · md 16 · lg 20 · xl 24 · xxl 32. Screen padding is
  typically `p-4` (16). Card padding `p-4`–`p-5`.
- **Shadow:** `shadow-card` for raised cards, `shadow-brand-glow` for the magenta
  hero card and primary CTAs. Shadows are soft and low; don't stack them.

---

## 6. Component recipes (build these with utilities — no component lib is shipped)

The React package ships **tokens + theme only**, so compose components with the
classes above. Canonical recipes:

**Card**
```tsx
<div className="bg-surface border border-default rounded-lg shadow-card p-4">…</div>
```

**Magenta hero card (wallet value)**
```tsx
<div className="bg-brand-gradient text-on-brand rounded-xl shadow-brand-glow p-5">
  <p className="text-body-md opacity-90">Wallet Value</p>
  <p className="text-display-lg tabular-nums-bv">$41,812.14</p>
</div>
```

**Primary button (magenta pill)**
```tsx
<button className="bg-brand text-on-brand rounded-md px-6 py-3 text-label-lg
                   transition-colors duration-fast hover:bg-brand-deep
                   focus-visible:outline focus-visible:outline-2
                   focus-visible:outline-offset-2 focus-visible:outline-brand">
  Send
</button>
```

**Secondary button (outline)**
```tsx
<button className="border border-default text-primary rounded-md px-6 py-3
                   text-label-lg hover:bg-surface-high">Send Payment</button>
```

**Timeframe pill row (1h · 8h · 1d · …)** — active = filled magenta:
```tsx
<div className="flex gap-2">
  {items.map((t, i) => (
    <button key={t}
      className={`px-4 py-1.5 rounded-pill text-label-md transition-colors duration-fast
        ${i === active ? 'bg-brand text-on-brand'
                       : 'bg-surface-high text-secondary border border-default'}`}>
      {t}
    </button>
  ))}
</div>
```

**Circular icon button (search / bell / nav)**
```tsx
<button className="grid place-items-center size-10 rounded-pill
                   bg-surface-high text-primary hover:bg-surface">
  <SearchIcon className="size-5" />
</button>
```
Active/primary variant: swap to `bg-brand text-on-brand`.

**Transaction row (amount + colored status)** — status color mapping:
- confirmed / gain → `text-success`
- pending → `text-warning`
- failed / loss → `text-danger`
```tsx
<div className="flex items-start justify-between px-4 py-3">
  <div>
    <p className="text-title-sm">Transaction ID: ba213456</p>
    <p className="text-body-sm text-tertiary">2am, July 6, 2018</p>
  </div>
  <div className="text-right">
    <p className="text-title-md text-brand tabular-nums-bv">৳1500</p>
    <p className="text-label-sm text-success">send successfully</p>
  </div>
</div>
```

**Risk / progress bar**
```tsx
<div className="h-2 rounded-pill bg-surface-high overflow-hidden">
  <div className="h-full bg-brand" style={{ width: '50%' }} />
</div>
```

---

## 7. Theming API

```tsx
import { useTheme } from '@/theme';

const { theme, resolvedTheme, setTheme, toggle } = useTheme();
// theme: 'light' | 'dark' | 'system' (the preference)
// resolvedTheme: 'light' | 'dark' (what's actually applied)
setTheme('dark');   // persists to localStorage under 'bv-theme'
toggle();           // flip light/dark
```

Under the hood the provider sets `class="dark"` + `data-theme="dark"` on
`<html>`; `tokens.css` and Tailwind's `darkMode` key off that. **You never need
to branch on theme in components** — use the semantic classes and both themes
just work.

---

## 8. Rules for Claude Code (do / don't)

**Do**
- Use semantic Tailwind classes (`bg-surface`, `text-secondary`, `border-default`).
- Put currency/percentages in `tabular-nums-bv`.
- Reach for the recipes in §6 before inventing new patterns.
- Keep magenta as the *only* accent. Status greens/oranges/reds are for
  transaction state only, not decoration.
- Respect the quality floor: visible `focus-visible` rings, works down to mobile
  width, honors `prefers-reduced-motion`.

**Don't**
- Don't hardcode hex values or use Tailwind's built-in palette (`bg-pink-500`,
  `bg-gray-900`, etc.) — always go through the tokens.
- Don't introduce a second accent color (no gold, no blue CTAs). One accent.
- Don't add heavy multi-layer shadows or borders thicker than 1px hairlines.
- Don't branch styling on `resolvedTheme` when a semantic token already covers it.
- Don't reduce the display/number sizes to "fit" — numbers are meant to be large.

**When adding a new token:** edit `tokens.css` (both `:root`/`.light` and
`.dark`), then expose it in `tailwind.config.ts`. Keep the two themes in sync and
update the table in §3.

---

## 9. Provenance / related themes

This is one of a family that shares the exact same file layout and API:
**Ember** (smart-home, orange-on-black), **Vermillion** (crypto, red+gold on
black), **Marigold** (butter-yellow on cream), **Blossom** (magenta wallet).
Blossom-Vermillion = Vermillion's structure + Blossom's magenta, light-first,
single accent. If you port another one in, keep this same
`tokens.css → tailwind → components` wiring so screens are swappable.
