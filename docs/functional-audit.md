# Functional Audit: Spec §17 Walkthrough & Phase 3 Verifications

This audit documents the walk of all ten operational beats of Spec §17 performed by hand against the running system and automated test suite (`tests/test_integration_beats.py`), along with verification of the Phase 2 & Phase 3 requirements.

## Ten Beats Walkthrough (Spec §17)

| Beat | Name | Status | Evidence / Verification |
|---|---|---|---|
| 1 | **Hook** | **works** | `tests/test_integration_beats.py::test_walk_ten_beats` verifies 5 agents present at base station `(2, 2)`, all statuses `idle`, simulation paused, clock shows `awaiting mission` (`orch.current_spec is None`). |
| 2 | **Mission** | **works** | Natural language prompt parsed into 3 INSARAG ASR phases (`asr=1, 2, 3`), sector extraction (`B`, `C`), task generation (`len(tasks) >= 6`), regret SSI auction executed, initial Foresight rollout produces candidate plans, signed `ASSIGN` decision logged with `FACT` classification. |
| 3 | **Launch** | **works** | `orch.step(15.0)` runs forward. Scouts 1 & 2 launch along search routes, relay-1 positions itself at optimal mesh location, Bayesian search prior decays (`initial_prior_sum > current_prior_sum`), `expected_aid > 0.0`. |
| 4 | **Uncertainty** | **works** | Injected false alarm detection at `(38, 14)` spawns `VERIFY` P2 task, scout arrives, survivor absent, task closed with signed `TASK_CLOSED` (`FACT`), posterior dropped to 0.05. Injected true detection at survivor cell spawns `VERIFY`, scout arrives, survivor confirmed, spawns `DELIVER` P1 task assigned to cargo drone with signed `ASSIGN` decision. |
| 5 | **Comms Loss** | **works** | Injected `COMMS_LOSS` on `rover-1` sets `connected=False`, triggers lease manager countdown (`lease.expires_t > t`), task remains held under lease without duplicate assignment by central brain. |
| 6 | **Aftershock** | **works** | Injected `AFTERSHOCK` at `(15, 8)` updates `observed_terrain` to `rubble`. Active rover on road cell `(14, 8)` detects blocked path, triggers autonomous A* detour (`[(14, 8), (15, 7), (16, 8)]`), logs `REROUTE` decision (`FACT`), stores previous path in `ghost_route`. |
| 7 | **Wind Shift** | **works** | Injected `WEATHER_CHANGE` (`wind_deg=270, wind_mps=7.0`) blows chemical plume toward active sector. Triggers `ESCALATE` decision with `VALUE` classification, creates active Pareto trade-off escalation dialog comparing `P-current` vs `P-repair`. |
| 8 | **Shield Refusal** | **works** | Operator issues manual dispatch command directing drone through dense toxic plume (`plume >= 0.50`). `SafetyShield.check_operator_command` rejects command under invariant `I3_NO_FLY_ZONE`, signs and logs `SHIELD_OVERRIDE` (`SAFETY`) record with refusal rationale. |
| 9 | **Replay** | **works** | Mission run records full cryptographic log digest chain. `tests/test_replay.py` replays states against signed records, verifying identical state reconstruction and hash integrity. |
| 10 | **Evidence** | **works** | CLI `evaluate` runs S against baselines B0 (greedy nearest), B1 (fixed relay), B2 (no lease) across held-out seeds with 95% bootstrap confidence intervals, writing verified records to `registry.jsonl`. |

---

## Phase 3 Scope & Requirement Verifications

1. **`POLICY_SET` Message & Verification**:
   - Commander policy presets travel over WebSocket as a native `POLICY_SET` message (`{"type": "POLICY_SET", "preset": "cautious" | "balanced" | "aggressive"}`).
   - Server handler updates orchestrator policy and logs a signed decision record: `kind="POLICY_CHOICE"`, `classification="POLICY"`, `chosen=preset`.
   - Verified by automated test: `tests/test_server_phase3.py::test_websocket_policy_set`.

2. **Schema Decision Kind Alignment (`SHIELD_OVERRIDE`)**:
   - Verified that decision kinds in the log match the schema lines 394 & 739 exactly: `SHIELD_OVERRIDE` (formerly `SHIELD_REFUSAL`).
   - Verified by automated tests: `tests/test_fidelity.py` (1,000 records) and `tests/test_integration_beats.py`.

3. **Offline Mumbai Basemap & PMTiles Range Requests**:
   - `public/mumbai.pmtiles` extracted using Protomaps CLI (v1.31.2) for Mumbai bounding box `[72.76, 18.88, 73.02, 19.32]` at zooms 0–15 (~16 MB).
   - Starlette/FastAPI custom route serves byte range requests with HTTP 206 Partial Content and `Accept-Ranges: bytes`.
   - Verified by automated test: `tests/test_server_phase3.py::test_mumbai_pmtiles_range_request`.

4. **Five Pre-Cached Offline Zones**:
   - Vile Parle West (default, 176 bldgs, 154 roads), Andheri (112 bldgs, 347 roads), Bandra (294 bldgs, 372 roads), Dharavi (508 bldgs, 173 roads), Colaba (38 bldgs, 64 roads).
   - Uncached zone request triggers graceful offline refusal: `{"status": "error", "reason": "offline: zone not cached"}`.
   - Verified by automated test: `tests/test_server_phase3.py::test_api_zones_generate_offline_check`.

5. **Unified Coordinate Transform**:
   - Python `samanvay.core.coords` (using `pyproj` EPSG:32643 UTM 43N) and TypeScript `src/utils/coordinates.ts` (analytical Transverse Mercator).
   - Roundtrip tests confirm zone corners invert to within 1 cm (< 0.00001 m).
   - Cell center mapping places drones directly over OSM building centroids.
   - Verified by automated test: `tests/test_coordinates.py`.

6. **Interactivity Features (Map as Control Surface)**:
   - **Zone picker**: Hover highlights zone footprint; click triggers smooth 700 ms camera ease-in and activates zone simulation.
   - **Epicentre placement**: Click or drag updates earthquake intensity field ($I = I_0 \exp(-d/d_0)$) and live district damage ranking.
   - **Targeted event injection**: Map crosshair click or agent targeting dispatches event with `origin: "operator_injected"`.
   - **Agent focus & follow**: Map or roster click highlights route, lease, battery reserve floor, and link to base; `Follow [F]` tracks agent.
   - **Inspection**: Flat hover readout in Plex Mono; clicking building shows damage class, collapse probability, belief mass.
   - **No-fly polygon**: Operator draws polygon on map; passes through Safety Shield (invariant I3) and logs `POLICY_CHOICE` or `SHIELD_OVERRIDE`.
   - **Operator override**: Task override passes through shield; if unsafe, refused and logged as `SHIELD_OVERRIDE`.
   - **Escalation preview**: Hovering option in Pareto dialog previews candidate routes and ghost futures; camera frames target area.
   - **Log row to map**: Clicking decision row highlights affected agent/cell and animates camera.
   - **Time scrubber in Operate**: When paused, scrubber allows reviewing the last 5 minutes of ticks using the signed log; resumes live on unpause.
   - **Camera presets & controls**: Plan, Oblique, Follow, Frame all. Keyboard shortcuts: Space (pause/play), 1-5 (speed), F (follow), Esc (cancel).
   - **Layer controls**: Text-only toggles with opacity sliders for Belief isolines and Ghost futures.
