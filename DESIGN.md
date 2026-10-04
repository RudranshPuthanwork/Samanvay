# SAMANVAY design system

This file is the single source of truth for every visual decision in the console.
Every UI file must conform to it. The `check:design` lint gate (`npm run check:design`)
enforces the machine-checkable subset. When a rule here and a rule in the spec
conflict on anything visual, this file wins (overrides listed in section 8).

---

## 1. Concept

SAMANVAY is an instrument. The reference points are a cartographic survey plate,
an air-traffic plotting display, and a printed engineering drawing: flat, dense,
exact, quiet. Information is separated by 1 px rules and tonal steps, never by
boxes with shadows. The map is the hero. Nothing on screen exists to decorate.

No landing page, no hero section, no marketing copy, no login, no onboarding,
no settings page, no about page.

---

## 2. Typography

Two families only, self-hosted via `@fontsource`:

- **IBM Plex Sans** (400, 500, 600) — labels and prose
- **IBM Plex Mono** (400, 500) — every number, identifier, coordinate, timestamp, hash

### Banned families

Inter, Roboto, Arial, system-ui (as a visible face), Poppins, DM Sans,
Space Grotesk, Outfit, Plus Jakarta Sans, Geist, Montserrat, Manrope,
and any serif display face used for flair.

### Type scale (px)

12 / 14 / 16 / 20 / 28. Body is 14. Nothing below 12.

Projector-critical figures (TTI, expected aid, battery) are 20 px or larger in
Plex Mono.

### Rules

- `font-variant-numeric: tabular-nums` on all figures
- Sentence case everywhere. No Title Case headings. No ALL-CAPS eyebrow labels
- Letter-spacing: 0 to 0.01 em. No wide tracking
- No gradient text, no text shadow, no stroke text
- Line height: 1.4 prose, 1.25 tables and logs
- Real glyphs for units: multiply sign is ×, minus is −, degree is °.
  No em dashes in UI copy
- If `@fontsource/ibm-plex-sans-devanagari` renders cleanly, show `समन्वय`
  beside the wordmark in `ink-3`; if not, omit it

---

## 3. Colour

Defined as CSS custom properties and Tailwind theme values. The Tailwind palette
is **replaced** (`theme.colors`, not `theme.extend.colors`) so default palette
classes cannot be used.

### 3.1 Dark theme (default)

| Token | Hex | Use |
|---|---|---|
| `ground` | `#101215` | App background |
| `surface` | `#161A1E` | Panel background |
| `surface-raised` | `#1D2227` | Table header, active row |
| `rule` | `#2A3036` | 1 px dividers |
| `rule-strong` | `#414A53` | Panel outlines, emphasis rules |
| `ink` | `#E8E6E1` | Primary text (warm off-white) |
| `ink-2` | `#A9ADB1` | Secondary text |
| `ink-3` | `#737A82` | Tertiary, disabled |
| `attention` | `#D8A24A` | Single accent: human needed or human chose |
| `fact` | `#74B08C` | FACT tag, healthy, connected |
| `policy` | `#8FA3B8` | POLICY tag (slate, not violet) |
| `safety` | `#CE5F51` | SAFETY tag, shield, no-fly, low battery |

### 3.2 Map and agent palette

Terrain:

| Element | Hex |
|---|---|
| road | `#3A424A` |
| open ground | `#1B2025` |
| building | `#2C3238` |
| rubble | `#6B5B47` |
| water | `#2E4A5A` |

Belief heat-map: single-hue ramp from transparent to `attention` at low alpha.

Agent colours (differentiated primarily by symbol shape and two-character label):

| Agent | Hex |
|---|---|
| scout-1 | `#B7C4CF` |
| scout-2 | `#C9B99A` |
| cargo-1 | `#9FBFA8` |
| rover-1 | `#BFA3A0` |
| relay-1 | `#A8B0B8` |

### 3.3 Light theme (projector)

Same token names. Ground `#F3F1EC`, surface `#FFFFFF`, ink `#15181B`,
attention darkened to `#8A5F10`. Every token checked to 7:1 contrast for body
text and 4.5:1 for all other text. Toggled by a text link in the header.
Choice held in memory only (no storage APIs).

### 3.4 Banned colours

- Any purple, violet, indigo, fuchsia, magenta, blue-violet (hue 250 to 330 deg
  at saturation above 15%)
- Any neon or high-saturation glow: cyan `#00FFFF` family, lime `#39FF14` family,
  hot pink, electric blue (HSL saturation above 85% with lightness 45 to 65%)
- Pure `#000000` backgrounds
- Pure `#FFFFFF` text on dark
- No gradients of any kind (backgrounds, buttons, borders, charts, map)
- No glow, bloom, or coloured shadows

---

## 4. Shape and depth

- **`border-radius: 0` everywhere.** Panels, buttons, inputs, selects, tooltips,
  dialogs, scrollbars, tags, focus rings, progress bars, toggles, checkboxes,
  the escalation modal, log rows, the canvas frame. Tailwind config zeroes every
  radius. The lint gate enforces it. Style `<input type="range">`, scrollbars
  and form controls explicitly so browser defaults do not bring corners back
- **No shadows.** Depth comes from a 1 px rule and a one-step tonal change.
  The escalation dialog uses a 1 px `rule-strong` outline over a flat scrim
- No glass, blur, translucency on chrome, frosted panels
- No pills, avatars, circular badges, round status dots in interface chrome.
  Status is a short text word in colour or a small filled square. (Circles that
  encode data on the map — radio-range rings — are geometry, not decoration.
  Agent markers are not circles)
- No decorative backgrounds: no grids, dots, noise, blobs, vignette
- No coloured left borders on panels, rows, or alerts
- Line weights: 1 px for rules, 2 px for emphasis and active routes. Snap to
  the device pixel grid

---

## 5. Layout

Single fixed-viewport application with no page scroll. Built for a projector.

### 5.1 Header (40 px)

Left: wordmark `SAMANVAY` in Plex Sans 600 (plus `समन्वय` in `ink-3` if the
Devanagari font renders). Right: scenario id, seed, simulation clock, speed,
play, pause, baseline selector, judge mode, report, theme. All controls are
text buttons with 1 px outlines. No icon buttons.

### 5.2 KPI line (32 px)

One ruled line of inline figures: expected aid, survivors aided, P1 at risk,
time to infeasibility, escalations per hour, agents lost. Label in `ink-3` at
12 px, value in Plex Mono at 20 px. Separated by 1 px vertical rules.
Not a row of tiles.

### 5.3 Body

Asymmetric two-zone split. Map (C1) takes about 62% width and full remaining
height. Right zone: vertical stack with 1 px rule separators and deliberately
unequal heights — agent table, Foresight (tallest), decision log (scrolls),
comms queue (thin). At 1366 x 768 the proportions hold and nothing overlaps.

### 5.4 Command line (36 px, bottom edge)

One text input prefixed by `>` in Plex Mono. Confirmed MissionSpec shown as an
ordered phase list that opens above it on submit. This is the only input
affordance besides injection controls.

### 5.5 Event injection

A single ruled row of text buttons above the command line: Aftershock,
Comms loss, Weather change, Battery fault, Agent failure, Detection. Each
shows its `origin` tag semantics (injected) in the log afterward.

### 5.6 Escalation dialog (C5)

Square-cornered panel over the right zone and part of the map. Rest of console
dimmed flat but visible. Contents: Pareto plot, one row per option (not a card)
stating what it trades, countdown to default, default marked, two actions.
Keyboard: arrow keys move between options, Enter selects.

### 5.7 After-action report (C7)

Full-viewport view reached from the header Report control with a Back control.
A view, not a tab. No persistent navigation anywhere.

### 5.8 Agent roster (C2)

A table with five rows (not cards): identifier, type symbol, link state,
battery bar with reserve tick, current task, lease countdown when silent.
Row height 36 px. Selecting a row highlights its route on the map.

### 5.9 Spacing

4 px base unit. Rhythm is deliberately unequal: 4 and 8 px inside a group,
16 and 24 px between groups, rules instead of padding where possible. Do not
apply one uniform padding value to every container. Do not centre things that
are not centred by their nature. Left-align labels, right-align numbers.

---

## 6. Map (C1)

One `<canvas>`, survey-plate visual language.

### 6.1 Terrain

Flat filled cells with 1 px hairlines between road and block where helpful.
No textures, no outlines on every cell.

### 6.2 Agent symbols (canvas path calls)

Allowed symbol set (drawn by code, no external images):

| Agent type | Symbol | Label |
|---|---|---|
| scout | upward triangle | `S1`, `S2` |
| cargo | square with centre cross | `C1` |
| rover | diamond | `R1` |
| relay | hexagon outline | `X1` |
| base | square outline with fill | `BS` |

Each carries a two-character label and an altitude-band tick. No circles for
agents. No emoji, no external icon images, no sprite sheets.

### 6.3 Overlays

- Radio links: 1 px `ink-3`, dashed and `safety`-tinted when broken
- Routes: 2 px dashed per-agent colour
- Re-plan ghost: old route at low alpha for 3 seconds
- Detections: small squares; confirmed survivor = filled square with urgency
  label in Plex Mono (`S1 crit`). False alarm = struck-through label
- Plume: solid current outline, dashed forecast outline
- Belief heat-map: single-hue ramp
- Scale bar and north indicator (`N` text + line)
- Attribution: `© OpenStreetMap contributors (ODbL)` in 12 px `ink-3`,
  lower-left corner, when the OSM map is in use

### 6.4 Layer toggles

Row of text controls along the bottom edge of the map: Belief, Plume, Radio,
Routes, Forecast. On/off shown by underline and weight, not icons.

### 6.5 Hover readout

Coordinates and cell values in Plex Mono, flat readout. No tooltip bubble with
a tail, no rounded callout.

---

## 7. Charts

Foresight fan chart (C3), Pareto plot (C5), comms VoI bars (C6), evidence
charts (C7). All follow the dataviz discipline:

- Direct labels instead of legends where possible
- No chart junk, no 3-D, no gradient fills, no rounded bars, no animated draw-in
- Square-ended bars, 1 px axes in `rule-strong`
- Tick labels in Plex Mono 12 px
- Confidence intervals as plain whiskers
- Tag colours used semantically (FACT result = `fact`, VALUE = `attention`),
  never as decoration
- Data from live FORECAST and registry messages, never from front-end constants

---

## 8. Spec overrides

| Spec says | This design uses instead |
|---|---|
| C4 colours POLICY purple | `policy` slate `#8FA3B8` |
| C2 "agent cards" | Five-row agent table |
| Tailwind defaults, `rounded` utilities | Palette replaced, radius zeroed, shadow zeroed |
| Framer Motion for dialog/log transitions | CSS only (section 9) |
| "Agents (icons with band badge)" | Canvas-drawn symbols from section 6.2 |
| "Event ripples" | Expanding square outline, 600 ms |
| Mission map "node icons" | Code-drawn symbols only |
| LLM-based mission parser | Grammar parser only (no LLM) |

---

## 9. Motion

Motion is functional and short.

### Permitted

- Re-plan ghost fade (3 s)
- Event marker: expanding square outline, fade over 600 ms
- Escalation countdown
- 120 ms colour change on row/toggle state
- 150 ms escalation dialog appearance

### Banned

- Entrance animations, fade-up on mount, staggered lists
- Parallax, hover lift, `scale` on hover, springs, bounce
- Pulsing indicators, shimmer skeletons
- Animated number count-ups (numbers change instantly)

### Implementation

- Easing: `cubic-bezier(0.2, 0, 0, 1)`. No `ease-in-out`
- No `transition: all` or `transition-all`
- `prefers-reduced-motion` disables every animation except the countdown

---

## 10. SVG allowlist

The only `<svg>` elements permitted in components are data charts rendered by
Recharts and d3. No decorative SVG, no icons, no illustrations, no logo marks.

---

## 11. Copy rules

Every visible string must be one of: a spec-defined term, a unit, a number,
an identifier, or text generated from a `DecisionRecord` template.

### Style

- Plain, specific, short. Sentence case
- No exclamation marks. No em dashes. No rhetorical questions

### Banned words

seamless, seamlessly, elevate, unlock, unleash, empower, supercharge,
revolutionary, revolutionize, next-gen, cutting-edge, state-of-the-art,
game-changing, effortless, intuitive, robust, leverage, delve, harness,
streamline, "powered by AI", "AI-powered" (except quoting the problem statement
title in the report), "smart", "insights", "dashboard", "mission control center",
"command center", "welcome", "get started", "lorem", "placeholder",
"coming soon", "oops", "something went wrong"

### Error copy

State what failed and what the operator can do:
`Link to scout-2 lost 14:32. Task search-C2 held under lease until 14:55.`

### Empty states

Factual: `No escalations`, `No detections`, `Awaiting mission`.

---

## 12. Anti-vibe-coding ban list (comprehensive)

Everything in sections 3–4 of the build prompt, consolidated. The lint gate
checks the machine-readable subset; the rest are enforced by code review.

### Already covered above

- Rounded corners (section 4)
- Shadows (section 4)
- Purple / neon accents (section 3.4)
- Icons, emoji, decorative SVG (section 10)
- Sidebar, tabs, multi-page navigation (section 5)
- Three-card / stat-tile layouts (section 5)
- Gradients (section 3.4)
- Glass / blur / translucency (section 4)

### Additional tells (all banned)

- Gradient text, glowing buttons, blurred blobs behind content
- Thick coloured border on one side of a card
- Pulsing green "Live" dots, "New" pills, "Beta" badges, status pills
- Wide-tracked uppercase eyebrow labels
- Icon glyphs inside tinted squares; emoji as bullets
- Centred hero with headline, subhead and two buttons
- "Trusted by" logo rows, testimonials, pricing, footer with fake links
- Dashboard cliches: sidebar with Home/Analytics/Settings, top bar with
  avatar and bell, search field that searches nothing, "Welcome back"
- Fake metrics (`+12%` arrows, `99.9% uptime`, sparklines, "John Doe")
- Default Tailwind / shadcn styling (zinc/slate greys, indigo focus rings,
  `ring-2 ring-offset-2`)
- Inter showing through, system-ui visible
- Uniform padding on every container
- Fade-up on scroll, staggered entrance, hover scale, skeleton shimmer
- Toast notifications for log events
- Tutorial comments, TODO, console.log, utils2, magic numbers, unused imports
- Scaffold residue: Vite logo, vite.svg, "Vite + React", counter, default README
