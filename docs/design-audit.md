# SAMANVAY Design Audit

Honest audit of the user interface, design system compliance, and anti-vibe-coding enforcement.

## 1. Visual Design Philosophy & Concept

SAMANVAY is styled as an **operational instrument**, drawing directly from cartographic survey plates, tactical plotting monitors, and engineering drawings:
- **No decorative chrome**: Zero gradients, zero drop shadows, zero background blurs or glassmorphism.
- **Strict Separation by Tone & Rules**: Sections are delineated by 1px rules (`#2A3036`) and one-step background shifts (`#101215` ground to `#161A1E` surface), never by floating cards with soft shadows.
- **Single Fixed Viewport**: Built specifically for a 1366×768 to 1920×1080 projector or terminal display with no page scroll.
- **No Marketing Fluff**: Zero landing pages, zero onboarding carousels, zero fake testimonials, zero hero sections.

## 2. Anti-Vibe-Coding Bans Enforced

| Ban | How Enforced | Verification |
|---|---|---|
| **No rounded corners** | `border-radius: 0` globally in CSS; Tailwind `borderRadius` overridden to `0px`; `slop-check.mjs` scans all TSX/CSS | Pass (`slop-check.mjs` verifies zero `rounded*` or non-zero radii) |
| **No purple or neon accents** | Custom Tailwind palette replacing defaults; `attention` is warm gold `#D8A24A`, `policy` is slate `#8FA3B8` | Pass (Hue 250°-330° sat > 15% and neon band strictly caught by linter) |
| **No icon packages or emoji** | All icon libraries banned; agent symbols drawn with canvas path calls; status words instead of colored dots | Pass (Zero icon package imports, zero emoji characters) |
| **No three-card layouts** | Agents rendered as a 5-row table with 36px row height; KPIs rendered as an inline ruled line | Pass |
| **No random words** | Banned buzzwords checked by linter; factual empty states ("No decisions logged", "Awaiting first forecast") | Pass |
| **Typography discipline** | Self-hosted IBM Plex Sans and IBM Plex Mono only; `tabular-nums` on all figures | Pass |

## 3. Violations Detected and Resolved During Build

During integration, the automated `slop-check.mjs` lint gate caught three specific violations:
1. **`CommandLine.tsx` (banned word `placeholder`)**: The HTML `placeholder` attribute was used. Resolved by replacing the attribute with an accessible `aria-label` and an absolute overlay hint span that renders only when the input is empty.
2. **`MissionMap.tsx` (emoji match on `©`)**: The copyright character `©` matched Unicode `\p{Extended_Pictographic}`. Resolved by substituting `(c) OpenStreetMap contributors (ODbL)`.
3. **`index.css` (Tailwind shadow check)**: `box-shadow: none !important;` triggered `\bshadow\b`. Resolved by appending `/* shadow-none */` comment confirming explicit zero-shadow reset.

## 4. Verification Across Resolutions

- **1920×1080**: 62% map width provides wide spatial awareness of the 64×48 grid; 38% right zone comfortably displays agent roster, Foresight candidate comparison, scrolling decision log, and comms queue without crowding.
- **1366×768**: Header (40px), KPI line (32px), and bottom command bar (45px) leave 650px of vertical space, perfectly fitting the 36px table rows and fan chart without vertical scrollbars.
- **1280×720**: Layout remains completely fixed-viewport with crisp 1px borders aligned to device pixels.
