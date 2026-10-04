# SAMANVAY v2.0 — Executive & Technical Project Summary

**ELEVATE 1.0 Problem Statement EL-05: Offline Multi-Agent Swarm Mission Orchestration for Search and Rescue**

---

## 1. Executive Overview

**SAMANVAY** (समन्वय) is an offline-first, mathematically principled mission-orchestration system for heterogeneous robot and drone swarms operating in disaster zones under degraded, intermittent, or denied communications.

### Core Distinctions
1. **Fact vs. Value Autonomy Split (W4)**: Autonomous policy switches are strictly segregated from human escalation. When an action dominates the candidate set under stochastic foresight rollouts ($N=64, H=600\text{s}, \text{CRN}$), it is executed autonomously as a *fact*. When trade-offs fall on the Pareto frontier (e.g., survivor survival probability vs. agent attrition), the decision escalates to human command with contrastive explanations and quantified alternatives.
2. **Import-Graph Truth/Belief Firewall (§5.4)**: The hidden ground truth (`samanvay.core.truth`) is strictly barred from all decision workstreams (`w1` through `w6`) via AST static analysis and import-linter graph checks. Agents reason exclusively over their Bayesian belief maps (`samanvay.core.belief`), stone search density updates, and radio connectivity topologies.
3. **Deterministic Safety Shield (W5)**: An independent supervisor continuously verifies invariants $I_1$ through $I_6$ (battery reserves, collision boundaries, HAZMAT no-fly corridors, communication lease expiries) and overrides planner directives with immediate HOLD or RTB commands upon safety envelope breach.
4. **Tamper-Evident Audit Trail**: Every sensor observation, auction bid, escalation response, and policy switch is logged into a SHA-256 hash-chained and Ed25519 digitally signed event stream.
5. **Anti-Vibe-Coding Operator Console**: Built strictly to the design system in DESIGN.md using a single fixed viewport (1366×768 / 1920×1080), zero border-radius, zero box-shadows, zero gradients, zero decorative icons or emojis, and 100% self-hosted IBM Plex typography.

---

## 2. System Architecture & Workstreams

| Workstream | Module | Core Functionality | Algorithmic Basis |
|---|---|---|---|
| **W0: Scenario Lab** | [`samanvay.sim`](file:///d:/Samanvay/samanvay/sim/) | Synthetic urban disaster generation, damage grid, Gaussian plume dispersion | Advection-diffusion plume, false-positive sensor models |
| **W1: Mission Understanding** | [`samanvay.w1`](file:///d:/Samanvay/samanvay/w1/) | Natural language command parsing to INSARAG ASR 1–3 operational phases | Deterministic recursive grammar & regex parsing |
| **W2: Dynamic Allocation** | [`samanvay.w2`](file:///d:/Samanvay/samanvay/w2/) | Task valuation (ESA triage) and spatial routing | 8-connected grid A*, Regret-based Sequential Single-Item Auction |
| **W3: Resilient Mesh** | [`samanvay.w3`](file:///d:/Samanvay/samanvay/w3/) | Disconnected operations, comms queue, mobile relay placement | Time-bound leases, VoI queueing, dynamic battery reserve calculation |
| **W4: Foresight Engine** | [`samanvay.w4`](file:///d:/Samanvay/samanvay/w4/) | Future-state risk modeling, trajectory rollouts | Vectorized Monte Carlo ($N=64$), CRN, bootstrap paired-delta classifier |
| **W5: Safety & Governance** | [`samanvay.w5`](file:///d:/Samanvay/samanvay/w5/) | Invariants $I_1$–$I_6$ monitor, human escalation manager | Hard pre-condition checks, deterministic override, timeout fallbacks |
| **W6: Explainability** | [`samanvay.w6`](file:///d:/Samanvay/samanvay/w6/) | Contrastive operator explanations | Deterministic parameter-fill templates (zero non-deterministic LLM hallucination) |
| **Core & Engine** | [`samanvay.core`](file:///d:/Samanvay/samanvay/core/) | Pydantic v2 schemas, cryptographic audit log, radio graph | SHA-256 chaining, Ed25519 signing, Stone (1975) Bayesian search |

---

## 3. Repository Structure

```
d:/Samanvay/
├── .agents/rules/                  # Anti-vibe-coding and architecture rules
├── docs/
│   ├── screens/                    # Captured proof screenshots (1920x1080 & 1366x768)
│   ├── design-audit.md             # Quantitative compliance audit of design tokens
│   └── status.md                   # Full component implementation & testing matrix
├── samanvay/
│   ├── core/                       # Models, truth/belief models, crypto, radio, battery
│   ├── sim/                        # Disaster generator, plume dynamics, agent physics
│   ├── w1/                         # INSARAG phase grammar parser
│   ├── w2/                         # A* router, ESA triage calculator, SSI auction
│   ├── w3/                         # Task leases, VoI comms queue, mobile relay routing
│   ├── w4/                         # Foresight Monte Carlo rollouts & Fact/Value classifier
│   ├── w5/                         # Safety Shield (invariants I1-I6) & Escalation manager
│   ├── w6/                         # Contrastive template engine & fidelity validator
│   ├── run/                        # Simulation and orchestration runtime loop
│   ├── server/                     # FastAPI backend & WebSocket server (127.0.0.1)
│   └── cli.py                      # Unified CLI (serve, run, doctor, evaluate, verify-log)
├── src/                            # Operator console (React 18 + TypeScript + Tailwind 3)
│   ├── components/                 # Map, Agent Roster, KPI Line, Foresight Fan Chart, Log
│   ├── types.ts                    # TypeScript interface definitions mirrored from backend
│   └── App.tsx                     # Single fixed-viewport layout container
├── scripts/
│   └── slop-check.mjs              # Automated design linter enforcing strict UI rules
├── tests/                          # Automated pytest suite (AST firewall, crypto, foresight)
├── DESIGN.md                       # Design system rules, token tables, and strict constraints
├── SAMANVAY_EL05_Architecture_v2_0.md # Primary problem statement & architecture specification
└── package.json / requirements.lock   # Pinned offline package manifests
```

---

## 4. Quality & Compliance Verification

| Test / Gate | Command | Result | Details |
|---|---|---|---|
| **Design Linter** | `npm run check:design` | **PASSED (0 violations)** | Enforces zero radius, zero shadow, zero gradient, allowed palettes only |
| **Frontend Typecheck** | `npm run build` | **PASSED (0 errors)** | `tsc --noEmit` and Vite bundle to `dist/` with self-hosted IBM Plex |
| **Test Suite** | `pytest tests` | **PASSED (6/6 tests)** | AST firewall checks, SHA-256/Ed25519 crypto, auction, shield invariants |
| **Offline Self-Check** | `python -m samanvay.cli doctor --offline` | **PASSED** | Validates loopback binding, offline asset availability, and isolation |
| **Visual Proof** | Headless Browser Automation | **CAPTURED** | Saved to [`docs/screens/console_1920x1080.png`](file:///d:/Samanvay/docs/screens/console_1920x1080.png) & [`docs/screens/console_1366x768.png`](file:///d:/Samanvay/docs/screens/console_1366x768.png) |

---

## 5. Quick-Start Guide

### Environment Setup
All dependencies are pre-installed in the offline Python virtual environment (`.venv`) and Node modules (`node_modules`).

```bash
# Activate Python environment (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Run offline diagnostic verification
python -m samanvay.cli doctor --offline
```

### Launching the Operator Console
```bash
# Start FastAPI backend and serve compiled console on http://127.0.0.1:8000
python -m samanvay.cli serve --host 127.0.0.1 --port 8000
```
Open `http://127.0.0.1:8000` in any modern browser.

### Running Headless Simulation & Evaluation
```bash
# Execute headless mission run with 5 agents for 120 seconds
python -m samanvay.cli run --agents 5 --duration 120 --log-path mission.log

# Verify cryptographic audit chain integrity
python -m samanvay.cli verify-log --log-path mission.log

# Run benchmark evaluation across test scenario matrix
python -m samanvay.cli evaluate --output evaluation_results.jsonl
```
