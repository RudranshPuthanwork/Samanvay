# SAMANVAY Component Status (Phase 3)

Current status of all architectural components and scope tiers (Spec §15 & §16, Phase 3 verified).

## Phase 3 Mumbai-Wide Map & Swarm Architecture

| Component | Module / Path | Status | Evidence |
|---|---|---|---|
| Offline Mumbai Basemap | `public/mumbai.pmtiles` & `samanvay.server.app` | **Built & Tested** | 16 MB PMTiles file (zoom 0–15) served via HTTP 206 Partial Content range requests (`tests/test_server_phase3.py`) |
| Pre-Cached Zone Library | `public/zones/*.json` & `/api/zones` | **Built & Tested** | 5 offline zones pre-cached: Vile Parle West (default), Andheri, Bandra, Dharavi, Colaba; uncached requests refused with `offline: zone not cached` |
| Unified Coordinate Transform | `samanvay.core.coords` & `src/utils/coordinates.ts` | **Built & Tested** | UTM zone 43N (EPSG:32643) roundtrips within 1 cm; tested in `tests/test_coordinates.py` |
| MapLibre + deck.gl Interleaved Engine | `src/components/MumbaiMap.tsx` | **Built & Tested** | Custom offline style from DESIGN.md tokens (no text/icon layers in style; text labels via deck.gl TextLayer in IBM Plex Sans) |
| Simulated Earthquake Intensity Field | `src/utils/earthquake.ts` | **Built & Tested** | Spec §6.1.3 attenuation field ($I = I_0 \exp(-d/d_0)$), draggable/clickable epicentre, live district damage ranking |
| Map Interactivity & Controls | `src/components/MumbaiMap.tsx` & `src/App.tsx` | **Built & Tested** | Zone picker, epicentre placement, targeted event injection, agent focus & follow, building/survivor inspect readout, no-fly polygon drawing, task override |
| Escalation Preview & Camera Choreography | `src/components/EscalationModal.tsx` & `MumbaiMap.tsx` | **Built & Tested** | Hover/focus previews candidate route and ghost futures; smooth 700ms camera flight to target and return |
| Time Scrubber in Operate | `src/App.tsx` | **Built & Tested** | Review last 5 minutes of simulation when paused using signed log; instant live resume |
| Canvas 2D Fallback Plate | `src/components/MissionMap.tsx` | **Built & Tested** | One-click toggle and automated WebGL context loss fallback |
| Commander Policy Presets (`POLICY_SET`) | `samanvay.server.app` & `src/App.tsx` | **Built & Tested** | Real `POLICY_SET` WebSocket message logged as `POLICY_CHOICE` decision record; schema kind `SHIELD_OVERRIDE` |

## Core Simulation & Reasoning Tiers

| Component | Module / Path | Status | Evidence |
|---|---|---|---|
| Core Schemas & Contracts | `samanvay.core.models` | **Built & Tested** | Pydantic v2 schemas validating WebSocket contracts |
| Truth / Belief Firewall | `samanvay.core.truth` & `tests/test_firewall.py` | **Built & Tested** | AST walk and import-graph check (`tests/test_firewall.py`) |
| Cryptographic Decision Log | `samanvay.core.crypto` | **Built & Tested** | SHA-256 chain and Ed25519 signatures verified in `tests/test_crypto.py` |
| W0 Scenario Lab (F1 & F4) | `samanvay.sim.scenario_generator` | **Built & Tested** | Generates synthetic urban disaster and quake damage |
| Physical Simulator | `samanvay.sim.simulator` | **Built & Tested** | Runs motion, battery drain, plume advection/diffusion, detections |
| W1 Mission Understanding | `samanvay.w1.grammar` | **Built & Tested** | Deterministic grammar extracts INSARAG ASR 1-3 phases (`tests/test_integration_beats.py`) |
| W2 A* Pathfinding | `samanvay.w2.distance` | **Built & Tested** | 8-connected grid search with traversability constraints |
| W2 Regret SSI Auction | `samanvay.w2.auction` | **Built & Tested** | Property-tested in `tests/test_auction_hypothesis.py` (no over-allocation, unique winners) |
| W3 Leases Protocol | `samanvay.w3.leases` | **Built & Tested** | Time-bound leases coordinate during radio silence; countdown rendered in UI |
| W3 Dynamic Battery Reserve | `samanvay.core.reserve` | **Built & Tested** | Property-tested in `tests/test_reserve_hypothesis.py` (monotonic in distance & wind) |
| W3 Mobile Relay Placement | `samanvay.w3.relay` | **Built & Tested** | BFS multihop mesh optimization |
| W3 Comms Queue | `samanvay.w3.queue` | **Built & Tested** | Rate-limited VoI prioritization |
| W4 Foresight Rollouts | `samanvay.w4.foresight` | **Built & Tested** | Vectorized Monte Carlo rollouts (N=64, H=600s, CRN) |
| W4 Fact/Value Classifier | `samanvay.w4.foresight` | **Built & Tested** | Bootstrap paired-delta test separating FACT and VALUE |
| W5 Safety Shield | `samanvay.w5.shield` | **Built & Tested** | Property-tested in `tests/test_shield_hypothesis.py` (Invariants I1 to I6) |
| W5 Escalation Manager | `samanvay.w5.escalation` | **Built & Tested** | Manages Pareto trade-off options and timeouts |
| W6 Contrastive Explanations | `samanvay.w6.templates` | **Built & Tested** | Template-driven with chosen vs runner-up and tags; tested in `tests/test_fidelity.py` (1000 records) |

## Quality, Test & Lint Metrics

- **Pytest Suite**: **24 / 24 passed** (`pytest tests -v` in 2.85s)
  - `tests/test_coordinates.py`: Zone corners roundtrip < 1 cm, drone at cell center over building footprint
  - `tests/test_server_phase3.py`: HTTP range requests (206 Partial Content), zone library endpoints, offline rejection, `POLICY_SET` WebSocket handler
  - `tests/test_shield_hypothesis.py`: Shield Invariants I1-I6 with Hypothesis
  - `tests/test_auction_hypothesis.py`: Auction feasibility & non-over-allocation with Hypothesis
  - `tests/test_reserve_hypothesis.py`: Dynamic reserve monotonicity with Hypothesis
  - `tests/test_fidelity.py`: 1000 contrastive explanation fidelity tests
  - `tests/test_replay.py`: Cryptographic replay determinism
  - `tests/test_smoke_mission.py`: 600s / 10-minute end-to-end smoke mission
  - `tests/test_integration_beats.py`: Hand walkthrough of all 10 beats
- **Design Lint Gate** (`npm run check:design`): **0 violations**
  - Strict checks for sentence case, letter-spacing <= 0.01em, no uppercase transforms, no glows/vignettes, no purple/neon, no rounded corners, no 3-card layouts, no random icons/words.
- **TypeScript Compilation** (`tsc --noEmit`): **0 errors**
- **Production Build** (`npm run build`): **0 errors**
- **Offline Property**: **PASS** (Zero external runtime network requests; all OSM vector data, fonts, PMTiles, and assets are local).
