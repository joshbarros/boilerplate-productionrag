# Design system — Editorial / Linear-app style

> Source-of-truth for the frontend implementation. Every decision below is anchored in a
> reference (Linear, Vercel/Geist, Cursor) and a reason.

## Mood

**Editorial / Linear-app.** Dark surface, monospace for data, serif for emphasis, sharp
micro-interactions, generous negative space. Feels like a research notebook, not a chatbot.
Premium, technical, focused.

## Reference palette

- **Linear.app** (2026): deep `#08090A` background, accent `#5E6AD2` (indigo-violet),
  text `#F7F8F8` with `#62636C` muted.
- **Vercel Geist** (2026): pure black `#000000` with single accent gradient
  (`bg-gradient-to-r from-indigo-400 to-cyan-400`), monospace for stats, sans for prose.
- **Cursor** (2026): flat backgrounds, sharp 6-12px radii, code is always mono, gradients
  reserved for AI-emphasis moments.

**Our decision** (own the system, don't copy):
- Background: near-black `#0A0A0B`
- Surface (cards): `#131316` with `1px` hairline borders `#1F1F23`
- Text primary: `#EDEDEF`
- Text muted: `#8A8A93`
- Accent gradient: `linear-gradient(135deg, #7C3AED 0%, #06B6D4 100%)` (violet → cyan)
- Used **only** for: primary CTA, AI badge, focus ring, key stats
- Warning (rejected_budget): `#F59E0B` (amber)
- Error: `#EF4444` (red)
- Success: `#10B981` (emerald)
- Code/JSON/IDs: `JetBrains Mono` 13px, line-height 1.5

## Typography

- **Display (h1, hero)**: `Instrument Serif` (italic for accents), 48–64px, tight tracking
- **Heading (h2, h3)**: `Inter` 600, 24–32px, tracking -0.02em
- **Body**: `Inter` 400, 14–16px, line-height 1.6
- **Mono (code, IDs, paths, JSON)**: `JetBrains Mono` 13px, `tabular-nums`
- **Eyebrow labels** (section headers, status pills): `Inter` 500 uppercase, 11px, tracking 0.08em, color muted

## Spacing & layout

- 4px base. Spacing scale: 4, 8, 12, 16, 24, 32, 48, 64
- Container: max-width 1200px, horizontal padding 24px
- Cards: 16px padding, 12px radius, 1px hairline border, NO shadow (use border for definition)
- Page vertical rhythm: 64px top padding on main pages

## Component principles

1. **Hairline > shadow.** Define surfaces with 1px borders, not drop shadows.
2. **Mono > color** for data. Numbers, IDs, paths in mono so they don't compete with prose.
3. **Gradient is rationed.** The violet→cyan gradient is your AI accent — use it for: the
   "Ask" button, the "AI" badge on the model picker, focus rings on inputs, the budget
   progress bar fill.
4. **Empty states are not sad.** Show a 1-line instruction ("Drop a PDF or ask a question
   about what's already indexed") with a small illustration or icon — no "No data found" lorem.
5. **Refusals are a feature.** When the system returns `not_found`, render it as a quiet,
   amber-tinted card with the icon and a 1-line reason. Not a red error toast.
6. **Citations are first-class.** Each citation is a small card with: page number (mono),
   excerpt text (serif italic), document title (sans muted), support score (tiny mono badge).
7. **Latency is visible.** Every response shows `2.3s · $0.0000` in mono at the bottom of
   the message — reinforces the cite-or-refuse + budget story.

## Motion

- Hover: 150ms ease-out
- Fade in: 200ms
- Page transitions: 250ms
- Citation expansion: 200ms height + opacity
- No bouncy springs. Linear-feel = restrained.

## Anti-patterns (NEVER do)

- ❌ Generic purple/blue chat bubble gradients
- ❌ Animated 3D logo on landing
- ❌ "AI" badge on every element
- ❌ Particle backgrounds, mesh gradients, blobs
- ❌ Tailwind stock buttons (we use our own composition)
- ❌ shadcn's default theme (we re-token the colors)

## Pages

### `/` — Chat
- Top: thin nav bar (logo, model picker, budget pill, user)
- Center: scrolling conversation
- Bottom: composer (multiline, send on Cmd+Enter)
- Sidebar (collapsible, 280px): session list, "New chat"
- When answer arrives, the **citations rail slides in from the right** (320px)
  showing the source page excerpts inline with the answer.

### `/ingest` — Documents
- Drag-and-drop zone (large, dashed border, gradient on hover)
- Per-file row: filename (mono), status pill (succeeded/failed/duplicate/ocr), page count, latency
- Active uploads show a thin gradient progress bar

### `/budget` — Budget dashboard
- Big number: **$2.34 / $5.00 daily** (mono, gradient fill on the bar)
- Two stat cards: query cap · rejected count
- "Recent activity" timeline (last 20 queries) with mono cost & latency

## Implementation order

1. Tailwind v4 config with custom tokens (no shadcn defaults)
2. shadcn/ui install with `--base-color=neutral` + custom CSS variables
3. App shell: layout, nav, theme
4. Composer + message list (the chat primitive)
5. Citation cards + refusal cards
6. Ingest page
7. Budget dashboard
8. Wire all three to live backend (`apps/backend` on port 8800)
