# SAMANVAY

Offline mission-orchestration system for a heterogeneous robot and drone swarm.
ELEVATE 1.0 (Problem Statement EL-05).

## System Overview

SAMANVAY coordinates mixed aerial and ground assets (scouts, cargo drones, ground rovers, and mobile radio relays) for urban search and rescue.

Key capabilities:
- **Offline Single-Process Architecture**: Operates on a field laptop with all network access disabled; serves a console and WebSocket bound to 127.0.0.1.
- **Fact/Value Autonomy**: Foresight Monte Carlo rollout engine (N=64, H=600s, Common Random Numbers) evaluates candidate plans; bootstrap paired-difference test separates autonomous switches (FACT dominance) from human escalations (VALUE trade-offs with Pareto options).
- **Independent Safety Shield**: Monitors invariants I1-I6 (no-fly plume breach, dynamic battery reserve, geofence, altitude separation, payload validity) and forces HOLD or RTB overrides.
- **Cryptographic Audit Log**: Every decision is hash-chained with SHA-256 and digitally signed at mission completion using Ed25519.
- **Strict Truth/Belief Firewall**: Planners and rollouts operate strictly on the BeliefState; Ground truth (TruthWorld) is isolated in simulation and evaluation.

## Environment and Dependencies

- Python: 3.11 (`.venv`, pinned in `requirements.lock`)
- Node.js: 20 LTS (`package.json`, pinned in `package-lock.json`)
- Fonts: Locally bundled IBM Plex Sans and IBM Plex Mono (no external CDN)

## Installation

```bash
# 1. Python virtual environment
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.lock

# 2. Node packages
npm ci
```

## Build and Quality Gates

```bash
# 1. Run design lint gate and compile frontend console
npm run build

# 2. Run Python test suite (firewall, crypto, shield, foresight, auction)
.\.venv\Scripts\pytest

# 3. Verify offline self-check
.\.venv\Scripts\python -m samanvay.cli doctor --offline
```

## Running the System

### Start the Console Server

```bash
.\.venv\Scripts\python -m samanvay.cli serve --host 127.0.0.1 --port 8000
```
Open `http://127.0.0.1:8000` in a browser.

### Headless Mission Execution

```bash
.\.venv\Scripts\python -m samanvay.cli run --duration 60
```

### Benchmark Evaluation

```bash
.\.venv\Scripts\python -m samanvay.cli evaluate --runs 10
```

### Audit Decision Log

```bash
.\.venv\Scripts\python -m samanvay.cli verify-log report.json
```

## Repository Structure

```
├── samanvay/
│   ├── core/           # Frozen models, constants, crypto, belief, and truth
│   ├── sim/            # W0 Scenario Lab and physical simulator
│   ├── w1/             # W1 Deterministic grammar mission understanding
│   ├── w2/             # W2 Regret SSI auction, A* router, and ESA currency
│   ├── w3/             # W3 Radio mesh, leases, reserve, and VoI comms queue
│   ├── w4/             # W4 Foresight Monte Carlo rollouts and classifier
│   ├── w5/             # W5 Safety shield invariants and escalation manager
│   ├── w6/             # W6 Contrastive templates and fidelity testing
│   ├── run/            # Central orchestrator wiring workstreams
│   ├── server/         # FastAPI loopback server and WebSocket handler
│   └── cli.py          # Unified CLI entry point
├── src/                # React console conforming to DESIGN.md
├── scripts/
│   └── slop-check.mjs  # Design lint gate enforcing anti-vibe-coding rules
├── tests/              # Test suite including truth/belief firewall AST checks
├── DESIGN.md           # Visual design specification
└── requirements.lock   # Pinned Python dependencies
```
