# SAMANVAY v2.0 — Final Architecture for ELEVATE 1.0 · EL-05
### AI-Powered Autonomous Robot & Drone Swarm Mission Orchestration

| | |
|---|---|
| **Problem statement** | EL-05 · ELEVATE 1.0 · D. J. Sanghvi College of Engineering (DJS NSDC) — *"demonstrate mission-level autonomy and swarm coordination, rather than solving an isolated capability such as object detection, SLAM, or obstacle avoidance"* |
| **Gates** | Idea / PPT submission and hackathon build `[VERIFY: organisers — exact dates, build duration, team size, whether pre-written code is permitted]`. This document assumes a team of 4 and a 32-hour on-site build `[ASSUMPTION]`. |
| **Document status** | v2.0 final architecture. It audits and supersedes the v1.0 blueprint ("SwarmCommand — EL-05 Architecture & Build Blueprint", 3 October 2026). §2 records every defect found in v1.0; §24 records every decision that changed. The body carries only the decision now in force. ★ marks components that are new since v1.0, as a build-status label for the team. |
| **Working name** | **SAMANVAY** (समन्वय — *coordination*). Tagline: **"Many machines. One accountable mission brain."** The v1.0 name SwarmCommand remains acceptable if the team prefers it; nothing in the design depends on the name. |

**Conventions.** `[ASSUMPTION]` believed, unverified · `[ESTIMATE]` must be measured and replaced · `[VERIFY: …]` confirm against the named source · `[TARGET]` a value we commit to measuring against · `[POLICY]` a value the *operator* sets, never a constant of nature. Every threshold is either a procedure or a declared policy. Every method carries a citation. Every capability carries a declared failure mode. All simulation parameters (speeds, ranges, endurance, detection rates) are tunable scenario parameters chosen by us, not measurements of real hardware, and are presented that way on every slide.

---

# Part I — Orientation

Part I exists so that any reader — a teammate joining late, a mentor, a judge — can understand what is being built and why before meeting the specification in Part II. Nothing in Part I is a design decision; where Part I and Part II appear to differ, Part II is authoritative.

## 0.1 Technology explained

An **API** is a defined way for one piece of software to call another. A **simulation tick** is one step of simulated time; everything in the world advances by the same step. A **WebSocket** is a long-lived two-way connection between the browser and the server, used here so the map updates without the page asking repeatedly.

Every choice below is judged against four constraints that never relax: it must run on one laptop with no internet, it must be explainable by a student to a judge, it must be buildable by four people in the time available, and it must produce a demo that cannot be confused with an animation.

| Technology | What it is | Why it, and not the alternative |
|---|---|---|
| **Python 3.11** | The language of the simulation, planner and evaluation | The team writes Python; NumPy vectorisation makes the rollout engine (§6.5) fast enough without a compiled language. 3.11 rather than the newest minor because every dependency here ships wheels for it. |
| **NumPy** | Arrays and vectorised arithmetic | The Foresight engine advances 64 possible futures simultaneously as one array operation per step. A Python loop over futures would be roughly 50× slower `[ESTIMATE]` and would force a smaller, less informative rollout count. |
| **SciPy (`scipy.stats`)** | Statistical tests and distributions | Wilcoxon signed-rank and bootstrap confidence intervals for the evaluation (§10), Wilson intervals for rates. One-line calls a judge can check against a textbook. |
| **FastAPI + Uvicorn** | A small Python web server with WebSocket support | Serves the built console as static files and streams state over one WebSocket, all in **one process bound to 127.0.0.1**. Flask-SocketIO was the alternative; FastAPI's Pydantic integration validates every message against the frozen schemas for free. |
| **Pydantic v2** | Data validation from Python type hints | The same models validate LLM output, WebSocket messages, scenario files and decision records. This is what lets four people build in parallel: a module that emits an invalid document fails CI. |
| **React 18 + Vite** | Front-end UI framework and build tool | The team already writes React. Vite builds the console into static files that FastAPI serves, so the delivered system has no Node.js runtime at demo time. |
| **HTML Canvas 2D** | The browser's immediate-mode drawing surface | Draws a 64×48 grid, five agents, paths, comm links and a heat-map at 60 fps with no extra library. PixiJS (WebGL) is smoother for effects but adds a learning curve; Leaflet/MapLibre need map tiles, which need internet. |
| **Recharts + D3 (scales only)** | Charting | The Foresight fan chart, the Pareto escalation plot and the evaluation charts. Recharts for standard charts; D3 scales for the custom Pareto plot with confidence ellipses. |
| **A\* search** | Shortest-path search on a grid with a heuristic (Hart, Nilsson & Raphael 1968) | Optimal on a grid with an admissible heuristic and fast at this size (< 5 ms per query `[ESTIMATE]`). D\* Lite is faster for incremental re-planning on large maps — unnecessary at 3,072 cells. |
| **Sequential single-item auction with regret** | A task-allocation method where tasks are sold one at a time to the agent with the cheapest bid (Koenig et al. 2006, AAAI; Lagoudakis et al. 2005, RSS) | Fast, explainable bid by bid, and with a known quality track record for multi-robot routing. Hungarian assignment handles only one task per agent; full optimisation (OR-Tools) is used as a *baseline* rather than the core because its decisions cannot be explained bid by bid. |
| **Google OR-Tools** | An optimisation library with a vehicle-routing solver | Used only as **baseline B3** (§10.3): a strong optimiser given the same information, so our planner is compared against something better than a strawman. Never in the decision path. |
| **OSMnx + Shapely** (build time only) | Downloads and processes OpenStreetMap road and building data | Turns a real Mumbai neighbourhood into the simulation grid once, at build time, cached to a JSON file. Not needed at demo time. OpenStreetMap data is ODbL-licensed; attribution is printed on the map. |
| **An LLM with JSON output** (hosted or local) | Turns a typed mission into a structured mission specification | Used only for language understanding (§6.2). It never allocates, routes, or decides. Every response is cached and a rule-based parser covers the demo missions, so the demo works with the API unreachable. |
| **SHA-256 (`hashlib`) + Ed25519 (`cryptography`)** | A cryptographic hash and a digital signature scheme | The decision log is hash-chained and signed at mission end (§6.7), so an after-action review can prove that no decision record was altered — a "flight recorder" for the swarm. Ed25519 because it has no nonce-reuse failure mode and 64-byte signatures. |
| **pytest + Hypothesis** | Unit testing and property-based testing | Hypothesis generates thousands of random scenarios to check safety invariants (§11): no agent ever enters a no-fly cell, no task ever goes to an incapable agent. Example-based tests can pass while an invariant is false. |

## 0.2 The solution explained

### The problem in one paragraph

After an earthquake, a response team may have two scout drones, a cargo drone, a ground robot and a relay drone — five machines with different speeds, batteries, sensors, radios and limits. Today each is flown or driven by its own operator, and the operators coordinate by shouting. When a battery runs low, a road is blocked by an aftershock, a robot loses radio contact, or a survivor is spotted, the plan has to change for everyone at once, in seconds, and a human cannot recompute five machines' plans that fast. A planner that does it automatically raises a harder question: which decisions should a machine make alone, and which belong to a human? SAMANVAY is the mission brain that coordinates the whole team, re-plans continuously, and knows the difference.

### The shape of the system

There are two halves, separated by a line that is never crossed at run time.

**Build-time** is our machines, with internet allowed. It contains the scenario lab (which generates disaster scenarios with exact hidden ground truth), the OpenStreetMap import, the evaluation harness and the baselines. None of this is needed to run a mission.

**Run-time** is one Python process on one laptop with no internet. It holds the world, the planner, the console server and the flight recorder.

### `samanvay.core` — the shared foundation

One package owned by one person. It holds the frozen schemas, the clock, the seeded random-number streams, the **two separate world views** — `TruthWorld` (what is really there, known only to the simulator) and `BeliefState` (what the swarm has observed) — and the **agent adapter interface**, through which the planner commands agents without knowing whether they are simulated or real. Every other module imports core and nothing else. The truth/belief split is enforced in code: planning modules cannot import `TruthWorld`, and a test fails the build if one does. This is what makes the demo honest — the planner never peeks at where the survivors really are.

### W0 — Scenario Lab

Manufactures the ground truth. From a map (synthetic or OpenStreetMap), an epicentre and a seed, it generates building damage, rubble that blocks roads, hidden survivors with urgency levels, a smoke plume that drifts with the wind, and a schedule of disruptions. Each scenario is fully described by a configuration file and a seed, so any scenario can be regenerated exactly — which is why our measured numbers mean anything.

### W1 — Mission Understanding

Answers: *what is the swarm being asked to do?* Turns typed English into a validated **mission specification** whose phases follow the international urban search-and-rescue doctrine (INSARAG Assessment, Search and Rescue levels — §6.2). The operator sees and confirms the specification before launch.

### W2 — Allocation, Routing and Search

Answers: *who does what, in which order, by which route?* A regret-based sequential auction sells tasks to agents; A\* routes each agent through its own traversable terrain; a Bayesian search map decides where to look next and how much to believe a detection.

### W3 — Communications

Answers: *who can talk to base, what happens to an agent that cannot, and what is worth sending?* A connectivity graph rebuilt every tick, a relay-placement search, a **lease** protocol so that a silent agent's tasks are neither abandoned too early nor duplicated, and a message queue ordered by how much each message would change the plan.

### W4 — Foresight ★ (the USP — §7)

Answers: *how will each candidate plan play out, given everything we are unsure about?* It runs 64 possible futures of each candidate plan, sampled from the swarm's *belief* rather than the hidden truth, and compares plans on three outcomes: survival-weighted aid delivered, risk of losing an agent, and risk of failing a committed rescue. It decides when to re-plan, which messages matter, and — the central idea — **whether a decision is a question of fact the machine may settle, or a question of value that belongs to a human.**

### W5 — Safety Shield and Escalation

Answers: *what stops the planner doing something dangerous, and how does a human step in?* An independent monitor, sharing no code with the planner, checks every command against hard limits and overrides it if needed. The escalation manager presents the human with the options Foresight could not choose between, and the trade-off between them.

### W6 — Explanation and Accountability

Answers: *why did the swarm do that, and can we prove the record is genuine?* Every decision becomes a structured record, a contrastive sentence ("Cargo-1 instead of Rover-1, because…"), and an entry in a hash-chained, signed log that can be replayed exactly.

### The console

A React single-page application served by the same process. A live map, agent cards, the decision log, the Foresight fan chart, the escalation dialog with a Pareto plot, the communications queue, and an after-action report.

### How a run flows

1. The operator types a mission; W1 returns a specification; the operator confirms it.
2. W2 auctions the initial tasks and routes the winners; W5 checks every route; agents launch.
3. Every tick the world advances; sensors update the belief map; W3 rebuilds the radio graph and sends the most valuable messages.
4. On any event, and every 30 s of simulated time, W4 forecasts the current plan against alternatives. If one alternative is better on every count, the swarm switches on its own and logs why. If the alternatives trade one good against another, the swarm asks the human.
5. W6 records every decision. At mission end the log is signed and the after-action report is generated.

## 0.3 Concepts explained

**Multi-robot task allocation (MRTA).** Deciding which robot does which task. Gerkey & Matarić (2004, IJRR) classify the problem: here, each robot can do one task at a time (single-task robots), each task needs one robot (single-robot tasks), and robots hold *queues* of future tasks (time-extended assignment). That classification matters, because it rules out the simple one-to-one Hungarian method and points to auctions and routing.

**Auction and bid.** Think of a ride-hailing dispatcher. Each open task is a ride request; each robot works out what it would cost to fit that task into its current queue and "bids" that cost; the cheapest bid wins. **Regret** improves on plain greed: instead of selling the cheapest task first, sell first the task whose best bid most outperforms its second-best bid — the task you would most regret giving to the wrong robot.

**Belief versus truth.** The simulator knows exactly where every survivor is. The swarm does not; it holds a probability for each grid cell. When a scout scans a cell and sees nothing, that cell's probability falls; when it sees a heat signature, the probability rises — but not to certainty, because sensors produce false alarms. Bayes' rule is the arithmetic for this update (§6.3.4).

**Rollout (Monte Carlo simulation).** To ask "how will this plan go?", run the plan forward many times in a fast internal model, each time with different random draws for the things we are unsure of — how fast a battery drains, whether a scan detects a survivor, which way the smoke drifts. The spread of outcomes across 64 runs is the forecast.

**Common random numbers.** When comparing plan A against plan B, give both plans the *same* 64 random futures. The difference between them is then caused by the plans, not by luck, and far fewer rollouts are needed to tell them apart. This is a standard variance-reduction technique in simulation.

**Pareto dominance.** Plan A *dominates* plan B if A is at least as good on every outcome and strictly better on one. If A is faster to reach the survivor but riskier for the drone, and B is the reverse, neither dominates; choosing between them requires deciding how much drone risk a minute of a survivor's time is worth. That is a **value judgement**, and SAMANVAY treats it as one.

**Confidence interval.** A range that, under stated assumptions, contains the true value with a stated probability (95 % here). Two plans are only called different if their paired difference's interval excludes zero.

**Value of information (VoI).** How much better the decision becomes if a piece of information arrives. A survivor detection that would re-route two agents has high VoI; a routine position report has nearly none. When the radio link can carry only three messages per tick, send the three with the highest VoI.

**Lease.** A time-limited claim. When an agent goes silent, its tasks are not reassigned at once — it is probably still working — but they are not held forever either. Each assignment carries an expiry computed from the agent's own predicted completion time; when it expires, the task is released.

**Safety shield / Simplex architecture.** Separate the component that tries to be *good* (the planner) from the component that guarantees *safe* (a small, simple monitor). If the monitor sees a command break a hard rule, it overrides it. Sha (2001, IEEE Software) called this the Simplex architecture; Alshiekh et al. (2018, AAAI) applied the same idea to learning agents as "shielding". The planner can then be clever without being trusted.

**Hash chain.** Each log entry includes the hash of the previous entry. Altering any entry changes its hash, which breaks every link after it. Signing the final hash proves the whole log.

**Why thresholds must be procedures or policies.** If escalation fires when "confidence < 0.5", a judge asks where 0.5 came from; "we tried some numbers" is fatal. Every number in SAMANVAY is either derived by a stated procedure (a confidence interval, a reserve computed from the route back to the charger) or labelled `[POLICY]` — a value a mission commander sets, such as the acceptable risk to an agent. A policy is not a weakness to hide; it is the honest location of a human decision.

---

# Part II — Architecture

## 1. Executive summary

Disaster zones, mines, industrial plants and remote infrastructure increasingly receive several autonomous machines at once — aerial scouts, cargo drones, ground robots, radio relays — each with different sensors, speeds, batteries, payloads and radios. EL-05 asks for the layer above them: one system that turns a high-level objective into a coordinated multi-agent plan, keeps it valid while batteries drain, links drop, routes close and new targets appear, decides what is worth transmitting over a scarce link, recognises when the mission is no longer safely achievable, and knows when to hand a decision to a human.

SAMANVAY v2.0 is that layer, delivered as **a single offline process on one laptop** with a live mission console. It is demonstrated on a post-earthquake urban search-and-rescue mission over a real Mumbai neighbourhood rasterised from OpenStreetMap (synthetic map as the fallback), with five agents of four types, and it is evaluated against four baselines on scenario families it was never tuned on. Its distinguishing properties:

1. **It separates questions of fact from questions of value (the USP, §7).** A belief-sampled rollout engine (Foresight) forecasts every candidate plan through the swarm's own uncertainty. When one plan is better on every outcome, the swarm switches alone and logs why. When the remaining options trade survivor time against agent risk, the swarm stops and asks — because that exchange rate is a human judgement, not a technical one. The same engine decides when to re-plan and which messages to transmit, so re-planning, communication and escalation are driven by one forecast instead of three unrelated thresholds.
2. **The planner never sees the answer.** The simulator's ground truth and the swarm's belief are separate objects in code; planning modules cannot import the truth, and a CI test enforces it. Detections are uncertain both ways — missed survivors *and* false alarms — so verification is a real decision, not a formality.
3. **Safety does not depend on the planner being right.** An independent shield, sharing no code with the planner, vetoes any command that would enter a no-fly zone, strand an agent below its computed return-to-charger reserve, or break altitude separation (Simplex architecture, Sha 2001).
4. **Silent agents are handled correctly.** A lease protocol keeps a disconnected agent's tasks reserved for exactly as long as its own plan says it needs, then releases them — avoiding both abandonment and duplicated work.
5. **Doctrine-aligned missions.** Mission phases follow the INSARAG Assessment, Search and Rescue levels used by international USAR teams, so the decomposition reads as operational practice rather than invention.
6. **Evidence rather than assertion.** Every claim in the deck is a number from the evaluation registry, measured on held-out scenario families against four baselines up to an OR-Tools optimiser (Should tier), with paired statistics and confidence intervals.

**The sentence for a non-technical judge:** *"After an earthquake, rescuers will have drones and robots but no way to run them as one team. SAMANVAY is the team's brain: it plans for all of them, re-plans the moment anything changes, and — unlike any system we found — it can tell the difference between a decision a machine should make and a decision only a human should make, and it asks only for the second kind."*

---

## 2. Independent audit findings (against the v1.0 blueprint)

Seventeen findings against v1.0 as written. Severity: **C** critical (a judge collapses the section) · **H** high · **M** medium · **L** low.

| # | Sev | Finding in v1.0 | Why it matters | Fix in v2.0 | Where |
|---|---|---|---|---|---|
| IA-01 | C | **The bid cost adds incommensurable units with hand-tuned weights.** `w1·time + w2·energy ratio + w3·risk + w4·comms penalty`; the weights are exposed as sliders "to make the planner risk-averse". | Every allocation then depends on four numbers we chose. "Where do the weights come from?" ends the section. | One currency: **expected survival-weighted aid** (ESA, §6.3.2). Energy and comms become feasibility constraints, not cost terms. Risk to agents is kept as a *separate outcome*, never summed with aid — its exchange rate is a `[POLICY]` or a human decision (§6.5.5). | §6.3.2, §6.5 |
| IA-02 | H | **The auction appends tasks to the end of a queue and sells the cheapest pair first.** | Appending ignores cheaper insertion points; cheapest-first is known to be weaker than regret-based ordering. | Cheapest-insertion marginal cost and regret-based selection (Koenig et al. 2006). | §6.3.3 |
| IA-03 | C | **The baseline comparison grades our own homework.** We wrote the scenario, the planner and the "naive baseline". | A judge says "you beat a strawman on your own test." | Four baselines including an OR-Tools optimiser with the same information; tuning on one family only; frozen parameters; held-out families and seeds; an external sanity lane on published CVRP instances. | §10 |
| IA-04 | H | **Detection is one-sided.** Scouts miss survivors with probability 0.1 but never raise false alarms, so VERIFY is always confirmed. | Verification becomes theatre; "uncertainty" in the demo is cosmetic. | Bayesian search map with detection *and* false-alarm rates; posterior-gated VERIFY; false alarms appear in the demo. | §6.3.4 |
| IA-05 | C | **A disconnected agent "keeps executing its last plan" while the planner may reassign its tasks.** | Two agents fly to the same survivor while a second survivor waits: duplicated work under exactly the condition the PS names. | Lease protocol with expiry from the agent's own predicted completion; reconciliation on reconnect; onboard fallback rule. | §6.4.3 |
| IA-06 | H | **"Decision confidence = min of four 0–1 scores", escalate below 0.5.** None of the four mappings is defined; 0.5 is arbitrary. | The escalation logic — the most memorable demo moment — rests on undefined numbers. | Replaced by Foresight outcome distributions with confidence intervals; escalation by dominance test and declared `[POLICY]` floors. | §6.5 |
| IA-07 | M | **Battery reserve is a flat 20 %.** | Too much for an agent next to the charger, too little for one at the far edge in a headwind. | Reserve = energy to the nearest reachable charger along the agent's own traversable path × (1 + margin), margin from the drain-rate spread used in Foresight. | §6.4.2 |
| IA-08 | H | **Re-planning uses a fixed 15 % hysteresis and "local repair only for affected tasks".** | 15 % is arbitrary; local repair alone can leave a plan far from good after a large event. | Two-level: immediate local repair (< 100 ms), then background full re-solve; switch only if the paired forecast difference minus an explicit **switching cost** has a 95 % interval above zero. | §6.5.4 |
| IA-09 | M | **LLM output is non-deterministic and the "keyword fallback" is unspecified.** | Demo reproducibility; "what if the LLM is wrong?" | Mission DSL with schema; temperature 0; cache keyed by input hash; grammar-based fallback with stated coverage; a held-out paraphrase test set with a measured parse accuracy. | §6.2 |
| IA-10 | M | **Scripted events on a fixed seed invite "you tuned it to this run".** | The demo's credibility rests on one rehearsed path. | Judge mode: judge picks the seed and injects events freely; 1,000-run randomised robustness test with crash-free rate and invariant checks reported. | §10.6, §17 |
| IA-11 | H | **No independent safety layer.** A planner bug or a mid-path hazard expansion could route a drone into smoke. | A single component is trusted to be both optimal and safe. | Safety shield (Simplex): independent monitor, hard constraints, override to HOLD/RTB, every intervention logged. | §6.6 |
| IA-12 | M | **Weather change has no model.** "Expand no-fly zones and raise drain" is a sentence, not a mechanism. | Event 5 of the demo depends on it. | Wind vector field affects drone ground speed and drain; smoke plume advects with the wind as a cellular model; Foresight plans against the *forecast* plume. | §6.1.4 |
| IA-13 | M | **No deconfliction.** Two drones may occupy the same cell and altitude. | A judge from robotics asks "what stops them colliding?" | Altitude bands per drone (strategic separation); shield enforces band uniqueness; cooperative space-time A\* (Silver 2005) declared for multi-rover futures. | §6.3.5, §6.6 |
| IA-14 | H | **"Terminate part of the mission" — named in the PS — has no mechanism.** | A clause met by nobody. | Task shedding: Foresight generates candidates that drop the lowest-value tasks when P1 commitments are at risk; shedding a P1 task is always escalated. | §6.5.3 |
| IA-15 | M | **No operator-load model.** Escalations could arrive every few seconds. | A real operator would stop reading them. | Escalation rate limit, batching, priority queue; escalations per mission-hour is a reported metric with a target. | §6.6.3 |
| IA-16 | H | **The effort plan assumes 32 hours without checking whether pre-written code is allowed.** | If the rules forbid it, v1.0's Must tier does not fit. | Effort ledger in person-hours; two timelines (pre-building allowed / not allowed); cut order. | §14, §15 |
| IA-17 | M | **The truth/belief split is implied, not enforced.** The planner's code could read survivor positions directly. | One accidental import makes every result meaningless — and the honest demo claim false. | `TruthWorld` and `BeliefState` are separate types; import-linter rule plus a CI test that fails if any planning module imports `TruthWorld`. | §5.4 |

---

## 3. Re-decided design questions

v1.0 made several structural decisions by assertion. Each is re-decided here from constraints.

| # | Question | v1.0 decision | Re-decided | Reason |
|---|---|---|---|---|
| RD-1 | Where does the simulation run? | Python backend | **Kept: Python backend, one process** | The rollout engine needs NumPy; the team's strongest language is Python; the browser stays a thin viewer. |
| RD-2 | Web console or native desktop? | React in a browser | **Kept: React, served by the same process on 127.0.0.1** | Unlike a security tool, EL-05 has no constraint against a local listener; the team knows React; the visuals that matter (map, fan chart, Pareto plot) are cheapest in a browser. Argued in §8. |
| RD-3 | What is the LLM for? | Decomposition + optional rephrasing | **Narrowed: decomposition only, into a DSL; explanations are template-generated** | An LLM-rephrased explanation can contradict the decision record. Explanations must be provably faithful (§6.7). |
| RD-4 | Allocation core | Sequential auction | **Kept, upgraded: regret + cheapest insertion; OR-Tools as a baseline, not the core** | Explainability bid by bid; OR-Tools keeps us honest about quality. |
| RD-5 | 2D or 3D? | 2D | **Kept: 2D top-down, altitude as bands** | Mission-level autonomy is the brief; 3D costs time that belongs in the planner. |
| RD-6 | Synthetic or real map? | Synthetic grid | **Changed: real OpenStreetMap neighbourhood (Should), synthetic fallback (Must)** | A real street layout near the venue makes impact concrete; done at build time, so no internet risk at demo time. |
| RD-7 | Centralised or decentralised planning? | Centralised | **Kept centralised, with onboard fallback rules and leases** | Decentralised consensus (CBBA, Choi, Brunet & How 2009) is the right production direction but is not buildable and explainable in the time. Declared in §13 and §20. |
| RD-8 | How are disruptions triggered? | Operator buttons on a fixed seed | **Changed: buttons + judge mode + scheduled stochastic events from the scenario** | Removes the "tuned to this run" critique (IA-10). |

---

## 4. Requirements coverage matrix

Every clause of EL-05 (main problem statement **MP**, objectives **O**, deliverables **D**) mapped to its mechanism, re-verified against the final design. Confidence = our estimate that the clause is met in substance at demo time.

| Clause | Requirement (paraphrased) | Mechanism in v2.0 | WS | Tier | Confidence |
|---|---|---|---|---|---|
| MP-1 | Accept objective, environment, capabilities, constraints, real-time events → executable multi-agent plan | Mission DSL from typed objective (W1); scenario file supplies environment; agent-type registry supplies capabilities; event bus | W1, W0, core | Must | High |
| MP-2 / O1 | Decompose into tasks with dependencies, priorities, sequencing | INSARAG-phased task templates expanded into a task graph with `depends_on`; priorities from ESA urgency classes | W1, W2 | Must | High |
| MP-2 / O2 | Allocate by capability, location, battery, payload, comms, risk, priority | Regret auction with feasibility gates (capability, payload, battery reserve, comms coverage); risk as a separate Foresight outcome | W2, W4 | Must | High |
| MP-2 | Manage routes, energy, payload, communication, risk collectively | A\* per traversability class; reserve-to-charger constraint; relay placement; Foresight joint outcomes | W2, W3, W4 | Must | High |
| MP-3 / O3 | Continuously monitor and re-plan on new information and events | Event bus + 30 s periodic Foresight epochs; local repair + background re-solve; switch on paired forecast gain | W4, W2 | Must | High |
| MP-3 | Reassign tasks · change priorities · alter routes · reposition comms assets · terminate part of the mission | Re-auction; operator and automatic priority change; A\* re-route; relay re-placement; **task shedding** (IA-14) | W2, W3, W4 | Must (shedding: Should) | High · Medium for shedding |
| MP-3 / D3 | Disruptions: high-priority target found, comms loss, route inaccessible, weather deterioration, critical battery, agent failure | Handlers for all six; each exercised in the demo or in judge mode and in the 1,000-run robustness test | W2–W6 | Must | High |
| MP-4 / O4 | Decide which observations are worth transmitting | Message queue ordered by Foresight value of information, type table as fallback; per-tick bandwidth budget | W3, W4 | Should (VoI) · Must (type table) | Medium |
| MP-4 | Identify when the mission may no longer be safely achievable | Time-to-infeasibility (TTI) and P(P1 failure) from rollouts; mission-feasibility gauge | W4 | Must | High |
| MP-4 / D4 | Escalate to a human when autonomous confidence is insufficient | Fact/value classification: escalate on non-dominated trade-offs, on `[POLICY]` floor breaches, and on any P1 shedding | W4, W5 | Must | High |
| D4 | Explanations for major autonomous decisions | Template-generated contrastive explanations from decision records; fidelity test; FACT/VALUE/POLICY tags | W6 | Must | High |
| D1 | ≥ 3 heterogeneous agents with distinct capabilities and constraints | 5 agents, 4 types: scout drone ×2, cargo drone, ground rover, relay drone (§6.1.2) | W0 | Must | High |
| D2 | Dynamic allocation, reassignment, scheduling, routing, resource management | W2 + leases + reserve constraint; shown live | W2, W3 | Must | High |
| MP-5 | Mission-level autonomy, not an isolated capability | No perception, SLAM or obstacle avoidance is built; sensors are modelled by detection probabilities; all effort is in the mission layer | all | Must | High |
| — | Proposed solution and end-to-end architecture (all deliverables) | This document; §5 diagram; PPT §11 of v1.0 carried forward and updated in §17 | — | Must | High |

---

## 5. System architecture

### 5.1 Module diagram

```
 BUILD-TIME  (our machines · internet permitted · never needed to run a mission)
 ┌────────────────────────────────────────────────────────────────────────────────┐
 │ W0 SCENARIO LAB  map import: synthetic grid | ★OSM neighbourhood (osmnx)       │
 │                  quake model: intensity field → damage → rubble on roads       │
 │                  hidden survivors (urgency, location) · plume + wind · events  │
 │                  families F1 urban-quake · F2 flood · F3 industrial fire ·     │
 │                  F4 night/degraded-comms quake (HELD OUT)                      │
 │ EVAL HARNESS     baselines B0–B3 (★B3 OR-Tools) · seeds · registry · CI gate   │
 │                  ★external lane: CVRPLIB Augerat set A sanity check            │
 └───────────────────────────────┬────────────────────────────────────────────────┘
                                 │ files only: scenario.json · ground_truth.json
                                 │ map_grid.json · registry.jsonl
 ════════════════════════════════╪═════════════════════════════════════════════════
 RUN-TIME · ONE PYTHON PROCESS · ONE LAPTOP · NO INTERNET · BOUND TO 127.0.0.1
                                 ▼
 ┌──────────────────────────── samanvay.core ─────────────────────────────────────┐
 │ schemas/   frozen Pydantic models v2 + JSON Schema export                      │
 │ clock/     sim clock (Δt = 1 s) decoupled from wall clock (1×–10×)             │
 │ rng/       named seeded streams: truth · sensing · rollouts · events           │
 │ truth/     TruthWorld   (simulator only — ★import-forbidden to planners)       │
 │ belief/    BeliefState  (search map, known hazards, last-known agent states)   │
 │ adapter/   AgentAdapter protocol: send_plan · get_state · on_event            │
 │            SimAdapter (built) · ROS2Adapter / MAVLinkAdapter (future)          │
 │ registry/  agent types · task types (plugin protocols, §5.5)                   │
 │ recorder/  ★hash-chained decision log (SHA-256) · Ed25519 sign at mission end  │
 └──────┬──────────────┬──────────────┬──────────────┬──────────────┬────────────┘
        ▼              ▼              ▼              ▼              ▼
 ┌────────────┐ ┌──────────────┐ ┌─────────────┐ ┌──────────────┐ ┌─────────────┐
 │ W1 MISSION │ │ W2 ALLOCATE  │ │ W3 COMMS    │ │ ★W4 FORESIGHT│ │ ★W5 SHIELD  │
 │ UNDERSTAND │ │ ROUTE SEARCH │ │             │ │   (USP)      │ │ & ESCALATE  │
 ├────────────┤ ├──────────────┤ ├─────────────┤ ├──────────────┤ ├─────────────┤
 │ LLM → DSL  │ │ ESA currency │ │ radio graph │ │ belief-      │ │ independent │
 │ temp 0 +   │ │ regret SSI   │ │ BFS from    │ │ sampled      │ │ monitor:    │
 │ cache      │ │ auction +    │ │ base        │ │ rollouts     │ │ no-fly ·    │
 │ grammar    │ │ cheapest     │ │ relay       │ │ N=64, H=600s │ │ reserve ·   │
 │ fallback   │ │ insertion    │ │ placement   │ │ common random│ │ geofence ·  │
 │ INSARAG    │ │ A* per class │ │ ★leases +   │ │ numbers      │ │ alt. bands  │
 │ ASR phases │ │ reserve maps │ │ reconcile   │ │ outcomes:    │ │ override →  │
 │ operator   │ │ ★Bayes search│ │ msg queue   │ │ ESA·Ploss·   │ │ HOLD / RTB  │
 │ confirm    │ │ map (pd,pfa) │ │ budget B/tick│ │ Pfail · TTI │ │ escalation  │
 │            │ │ alt. bands   │ │ ★VoI order  │ │ switch test  │ │ queue, rate │
 │            │ │              │ │             │ │ ★FACT/VALUE  │ │ limit, Pareto│
 │            │ │              │ │             │ │  classifier  │ │ dialog      │
 └─────┬──────┘ └──────┬───────┘ └──────┬──────┘ └──────┬───────┘ └──────┬──────┘
       └───────────────┴────────┬───────┴───────────────┴────────────────┘
                                ▼  DecisionRecord[] · Escalation[] · Event[]
 ┌──────────────────── W6 EXPLANATION & ACCOUNTABILITY ───────────────────────────┐
 │ contrastive explanations from records (template, ★fidelity-tested)             │
 │ FACT / VALUE / POLICY tags · "why not" runner-up · flight recorder · replay    │
 │ after-action report (timeline · decisions · escalations · metrics)            │
 └───────────────────────────────┬────────────────────────────────────────────────┘
                                 ▼  WebSocket (127.0.0.1 only) + static files
 ┌──────────────────── CONSOLE · React + Canvas, served by the same process ──────┐
 │ C1 mission map (terrain · belief heat-map · plume forecast · radio links ·     │
 │    paths · re-plan ghosts) · C2 agent cards · C3 ★Foresight fan chart + TTI ·  │
 │ C4 decision log (FACT/VALUE tags, why-not) · C5 ★escalation dialog + Pareto    │
 │ plot · C6 comms queue with VoI bars · C7 after-action report + evidence charts │
 └────────────────────────────────────────────────────────────────────────────────┘
 ★ = new since v1.0
```

**How to read it.** Three things the diagram says. First, the double line separates what we need to *build and evaluate* the system from what is needed to *run a mission*; nothing above it is in the run-time path, so the demo cannot fail because of the internet. Second, `samanvay.core` is the only shared dependency — W1 through W6 import it and never each other, which is what lets four people build at once (§5.4). Third, W4 Foresight sits beside the planner rather than inside it: the allocator proposes plans, Foresight judges them, and the shield constrains them. That separation is what lets each be explained and tested on its own.

### 5.2 The single-process, offline property

`python -m samanvay serve` starts one process that holds the simulator, the planner, the shield, the recorder, and a FastAPI server **bound to 127.0.0.1 only**, which serves the pre-built console and one WebSocket. No external network call happens during a mission. The only optional outbound call is the LLM at mission entry; in demo mode it is replaced by the cache, and `samanvay doctor --offline` runs a full mission with all outbound sockets refused and prints the result. This matters for the deployment story (§19): a field laptop at a disaster site will not have reliable connectivity, and the mission brain must not depend on it.

### 5.3 Frozen inter-module contracts (schemas v2)

Frozen in hour 0–2 of the build (or in the first pre-event session, §15), changed only by a versioned bump. Every message on the WebSocket and every file between modules validates against these; CI fails on a violation.

#### 5.3.1 `ScenarioManifest` — W0 ground truth (one per scenario, never visible to planners)

```json
{
  "scenario_id": "F1_urban_quake_s0042",
  "family": "F1",
  "seed": 42,
  "map": {"source": "osm", "grid": [64, 48], "cell_m": 10,
          "origin_latlon": [19.1075, 72.8370], "attribution": "© OpenStreetMap contributors (ODbL)"},
  "quake": {"epicentre_cell": [10, 40], "intensity_decay_cells": 30},
  "survivors": [{"id": "S1", "cell": [41, 8], "urgency": "critical"}],
  "plume": {"source_cell": [30, 20], "growth_cells_per_min": 0.6, "wind_deg": 225, "wind_mps": 4},
  "scheduled_events": [{"t": 420, "type": "AFTERSHOCK", "cells": [[22, 31], [23, 31]]}],
  "agents": ["scout-1", "scout-2", "cargo-1", "rover-1", "relay-1"]
}
```

`origin_latlon` is a placeholder near the venue `[ASSUMPTION: choose the final neighbourhood in the build]`.

#### 5.3.2 `AgentState` (belief-side; what the planner sees)

```json
{
  "id": "scout-2",
  "type": "scout_drone",
  "pos": [33, 12], "alt_band": 2,
  "battery": 0.61, "drain_rate_est": 0.00071,
  "reserve_required": 0.18,
  "status": "executing",
  "connected": false, "last_heard_t": 512,
  "lease": {"task": "search-C2", "expires_t": 655},
  "payload": {"capacity": 0, "carrying": []},
  "route": [[33, 12], [34, 12], [35, 13]],
  "queue": ["search-C2", "rtb"]
}
```

`reserve_required` is computed, not configured (§6.4.2). `last_heard_t` and `lease` exist because the planner's view of a disconnected agent is a prediction, not an observation.

#### 5.3.3 `Task`

```json
{
  "id": "deliver-S1",
  "type": "DELIVER",
  "priority_class": "P1",
  "asr_phase": 3,
  "location": [41, 8],
  "requires": ["carry_medkit"],
  "depends_on": ["verify-S1"],
  "value_model": {"urgency": "critical", "p_real": 0.94},
  "status": "assigned", "assigned_to": "cargo-1",
  "created_by": "event:DETECTION:31",
  "shed": false
}
```

`priority_class` P1 = a committed rescue action on a verified survivor; P2 = verification of a detection; P3 = search. Shedding a P1 task always escalates (§6.5.3).

#### 5.3.4 `Event`

```json
{"id": 31, "t": 488, "type": "DETECTION", "source": "scout-2",
 "data": {"cell": [41, 8], "posterior": 0.41},
 "origin": "simulated"}
```

`origin` ∈ {`simulated`, `scheduled`, `operator_injected`, `judge_injected`}. The console and the after-action report always show the origin, so it is never ambiguous which events were scripted.

#### 5.3.5 `Forecast` ★ (emitted by W4)

```json
{
  "epoch": 17, "t": 655, "n_rollouts": 64, "horizon_s": 600, "crn_seed": 9917,
  "candidates": [
    {"plan_id": "P-current", "esa_mean": 2.41, "esa_ci95": [2.20, 2.63],
     "p_agent_loss": 0.03, "p_p1_fail": 0.22, "tti_s": 380},
    {"plan_id": "P-repair-cargo-via-plume-edge", "esa_mean": 2.71, "esa_ci95": [2.49, 2.90],
     "p_agent_loss": 0.19, "p_p1_fail": 0.08, "tti_s": null}
  ],
  "paired_deltas": [{"a": "P-repair-cargo-via-plume-edge", "b": "P-current",
                     "d_esa_ci95": [0.18, 0.41], "d_ploss_ci95": [0.11, 0.22]}],
  "classification": "VALUE",
  "reason": "non-dominated: higher aid and higher agent-loss risk, both intervals exclude 0"
}
```

#### 5.3.6 `DecisionRecord`

```json
{
  "id": 58, "t": 655, "kind": "ESCALATE",
  "classification": "VALUE",
  "trigger_event": 44,
  "forecast_epoch": 17,
  "chosen": null,
  "options": ["P-current", "P-repair-cargo-via-plume-edge", "P-rover-long-route"],
  "operator_choice": {"option": "P-rover-long-route", "t": 671, "operator": "op-1"},
  "explanation": "Two plans differ in what they trade: …",
  "prev_hash": "9b1c…", "hash": "e04a…"
}
```

`kind` ∈ {`ASSIGN`, `REASSIGN`, `REROUTE`, `RELAY_MOVE`, `SHED`, `SWITCH_PLAN`, `ESCALATE`, `SHIELD_OVERRIDE`, `LEASE_EXPIRE`}. `classification` ∈ {`FACT`, `VALUE`, `POLICY`, `SAFETY`}.

#### 5.3.7 `MissionSpec` — the DSL produced by W1

```json
{
  "phases": [
    {"asr": 1, "area": "all", "goal": "wide_area_assessment"},
    {"asr": 2, "sectors": ["B", "C"], "priority": 1},
    {"asr": 3, "trigger": "survivor_confirmed", "spawn": ["DELIVER:medkit"]}
  ],
  "constraints": [{"type": "comms", "rule": "maintain_link_all"},
                  {"type": "avoid", "hazard": "plume"}],
  "policy": {"max_p_agent_loss": null, "p1_fail_floor": 0.30,
             "exchange_rate_agent_loss_vs_esa": null}
}
```

A `null` exchange rate means *every* value trade-off is escalated. A commander may set it in advance (§19.2); decisions then made under it are tagged `POLICY` and cite the policy.

#### 5.3.8 WebSocket messages

| Direction | Message | Payload |
|---|---|---|
| Server → UI | `SNAPSHOT` | Full belief state, map layers, agents, tasks (on connect) |
| Server → UI | `TICK` | Deltas since last tick, KPIs, TTI |
| Server → UI | `FORECAST` | One `Forecast` |
| Server → UI | `DECISION` | One `DecisionRecord` with explanation |
| Server → UI | `ESCALATION` | Options, outcome vectors with intervals, Pareto data, deadline |
| Server → UI | `COMMS` | Queue contents, VoI scores, sent this tick |
| UI → Server | `MISSION_SUBMIT` / `MISSION_CONFIRM` | Objective text / approved `MissionSpec` |
| UI → Server | `INJECT_EVENT` | Event type and parameters, origin set by the server |
| UI → Server | `ESCALATION_RESPONSE` | Chosen option id |
| UI → Server | `SIM_CONTROL` | Play, pause, speed, seed, baseline selector, judge mode |
| UI → Server | `POLICY_SET` | Commander policy values (logged as a decision record) |

### 5.4 Ownership and integration rules

1. `samanvay.core` is owned by one seat with a named reviewer; after the schema freeze, changes need that reviewer.
2. Workstream packages `samanvay.w1 … w6` import only `samanvay.core`, never each other. The orchestrator `samanvay.run` wires them together.
3. **Truth/belief firewall.** `samanvay.core.truth` may be imported only by `samanvay.sim` and `samanvay.eval`. An `import-linter` contract and a pytest that walks the import graph both fail the build on a violation. W4's rollouts sample hidden quantities *from the belief*, never from the truth.
4. A CI job runs a 10-minute simulated mission on scenario `F1_s0001` and fails on any schema violation, any safety-invariant violation, or a change in the decision-log digest without a changelog entry (replay determinism).
5. Commands: `samanvay serve | run | replay | evaluate | doctor | scenario | verify-log`.

### 5.5 Extensibility interface

EL-05's scenario list — disaster zones, mines, industrial facilities, agricultural fields, oceans — means new agent types and task types must drop in without touching the planner. Two plugin protocols and the adapter make that true by design.

```python
@dataclass(frozen=True)
class AgentTypeSpec:
    id: str                         # "inspection_crawler"
    capabilities: frozenset[str]    # {"move_ground", "inspect_close", "carry_medkit"}
    traversable: frozenset[str]     # terrain classes it may enter
    speed_mps: float
    drain_per_s: Callable[[float, float], float]   # (speed, payload) -> battery fraction per s
    drain_cv: float                 # coefficient of variation, used by Foresight
    radio_range_m: float
    payload_capacity: int
    sensor: SensorModel | None      # footprint radius, p_detect, p_false_alarm

@dataclass(frozen=True)
class TaskTypeSpec:
    id: str                         # "INSPECT_PIPE"
    requires: frozenset[str]
    duration_s: Callable[[AgentTypeSpec], float]
    value: Callable[[TaskContext, float], float]   # ESA contribution if completed at time t
    exclusive: bool

class AgentAdapter(Protocol):
    def send_plan(self, agent_id: str, waypoints: list[Waypoint]) -> None: ...
    def get_state(self, agent_id: str) -> AgentState: ...
    def on_event(self, callback: Callable[[Event], None]) -> None: ...
```

The allocator reads `capabilities`, `traversable`, `payload_capacity` and `requires` to build feasibility; A\* reads `traversable`; the energy model reads `drain_per_s`; Foresight reads `drain_cv` and `sensor`. **Proof, not assertion:** a tutorial plugin `inspection_crawler` (≈ 40 lines) is added in the demo's judge-mode segment and immediately receives tasks it is capable of, with no planner change. The adapter is the answer to "would this run on real robots?": a ROS 2 or MAVLink implementation of the same three methods is the integration path (§19.4).

---

## 6. Workstream specifications

Conventions: **Time** = build-time or run-time. All run-time costs are `[ESTIMATE]` for an 8-core laptop until measured in the first integration milestone (§15) and replaced.

### 6.1 W0 — Scenario Lab (ground-truth factory)

**Purpose.** Produce missions with exact hidden ground truth and stochastic disruptions, so every metric in §10 is computed against known truth rather than asserted. **Inputs.** Map source, family, seed. **Outputs.** `ScenarioManifest` (§5.3.1), `map_grid.json`, ground truth visible only to the simulator and the evaluator. `samanvay scenario --family F1 --seed 42` regenerates any scenario exactly. **Time** build (generation) and run (the simulator executes it).

#### 6.1.1 Map

The area is a 64 × 48 grid of 10 m cells — 640 × 480 m, about the size of a city ward block `[ASSUMPTION: scale]`. Terrain classes: `road`, `open`, `building`, `rubble`, `water`, `base`, `charger`.

- **Synthetic (Must).** Jittered street grid with building blocks; parameters in the family config.
- **OpenStreetMap (Should).** `osmnx.graph_from_point(origin, dist=400, network_type="drive")` for roads and `osmnx.features_from_point(origin, tags={"building": True}, dist=400)` for footprints, projected to metres, rasterised with Shapely (road centrelines buffered by 6 m). Run once at build time and cached; the cache file ships with the demo. Attribution "© OpenStreetMap contributors" is drawn on the map (ODbL). **Fallback:** if the import produces disconnected road networks, the largest connected component is kept and the rest is marked `open`.

#### 6.1.2 Agent roster (tunable scenario parameters — not hardware claims)

| Agent | Type | Speed | Endurance | Sensor (footprint, p_detect, p_false_alarm per cell-scan) | Radio range | Payload | Traversable |
|---|---|---|---|---|---|---|---|
| Scout-1, Scout-2 | Quadcopter, thermal camera | 8 m/s | 25 min | high band: r = 2 cells, 0.75, 0.003 · low band: r = 1, 0.90, 0.001 | 300 m | 0 | all except no-fly |
| Cargo-1 | Heavy-lift drone | 5 m/s | 18 min loaded / 28 min empty | none | 300 m | 1 medkit | all except no-fly |
| Rover-1 | Ground robot | 1.5 m/s | 120 min | close range: r = 1, 0.98, 0.0005 | 150 m | 4 kits | road, open |
| Relay-1 | Hover relay drone | 6 m/s | 40 min | none | 600 m | 0 | all except no-fly |
| Base | Fixed station + charger | — | — | — | 400 m | — | — |

All values `[ASSUMPTION]`, chosen so that each agent type is *necessary* for some part of the mission: scouts find, the rover verifies and carries volume but cannot cross rubble, the cargo drone reaches what the rover cannot but carries one kit, the relay is the only way to keep the far sectors in contact.

#### 6.1.3 Earthquake, damage and survivors

1. Intensity per cell: `I(c) = I₀·exp(−d(c, epicentre)/λ) + ε`, `ε ~ N(0, 0.1)`.
2. Building collapse probability `σ(k·(I − I₅₀))`; damage class 0–3 by thresholds on `I`.
3. A collapsed building spills rubble into each adjacent road cell with probability 0.5 — this is what blocks roads for the rover.
4. Survivors: count `K ~ Poisson(μ · n_collapsed)`, capped at 12; locations sampled with weights collapsed 5 · damaged 2 · intact 0.5 · open 0.1 `[ASSUMPTION]`; urgency critical / serious / stable with probabilities 0.2 / 0.5 / 0.3 `[ASSUMPTION]`.
5. **The swarm's initial belief is not the truth.** The belief prior is computed from building footprints and the *expected* intensity field (an epicentre is public within minutes of a quake), not from the realised damage. Belief and truth therefore start different, and the search has something real to discover.

#### 6.1.4 Plume and wind (fix for IA-12)

Hazard density `h ∈ [0, 1]` per cell, updated every 10 s of simulated time: advection by the wind vector (semi-Lagrangian shift with bilinear interpolation), diffusion by a 3 × 3 kernel, emission at the source. Wind direction follows a random walk (σ = 5°/min). `WEATHER_CHANGE` raises wind speed and rotates it. Drones: ground speed = airspeed + along-track wind component; drain multiplier `1 + 0.03 · max(0, headwind m/s)` `[ASSUMPTION]`. No-fly where `h ≥ 0.5` `[POLICY default]`.

#### 6.1.5 Events

Scheduled events from the manifest, plus stochastic ones: aftershocks (Poisson, mean one per 10 min, each adds rubble near collapsed buildings), link degradation episodes, agent faults (hazard 0.002 per agent-minute) `[ASSUMPTION]`. Operator and judge injections arrive through the same event bus with their `origin` recorded.

#### 6.1.6 Scenario families

| Family | What changes | Used for |
|---|---|---|
| F1 urban quake | Baseline family; OSM or synthetic map | Tuning (seeds 0–49) and in-family test (seeds 1000–1099) |
| F2 flood | `water` cells cover low roads; rover severely limited; drones dominate | Held-out test |
| F3 industrial fire | Large plume, frequent wind shifts, few survivors, high agent risk | Held-out test |
| F4 night, degraded comms | Lower p_detect, radio ranges × 0.6, more link episodes | Held-out test — the hardest family, never seen in tuning |

#### 6.1.7 Failure modes

The world is a stylised grid; real rubble, voids and building interiors are not modelled; survivors are points with an urgency label. These are stated on the architecture slide. The scenario lab's job is not realism but **known truth with realistic structure of uncertainty**, which is what an evaluation needs.

### 6.2 W1 — Mission Understanding

**Purpose.** MP-1, O1: turn a typed objective into a validated, executable mission specification. **Inputs.** Objective text, map summary (sector names, hazards, agent types). **Outputs.** `MissionSpec` (§5.3.7). **Time** run. **ML** an LLM, used only for language.

#### 6.2.1 Doctrine alignment — INSARAG ASR levels

International urban search-and-rescue teams structure operations by Assessment, Search and Rescue (ASR) levels (INSARAG Guidelines Vol. III, Annex B20): ASR 1 wide area assessment to build the sectorisation plan; ASR 2 sector assessment to identify viable live-rescue sites; ASR 3 primary search and rescue; ASR 4 secondary search and rescue through survivable voids; ASR 5 full coverage. SAMANVAY's mission phases map directly onto the first three:

| ASR | SAMANVAY phase | Tasks generated | Agents typically chosen |
|---|---|---|---|
| 1 | Wide-area sweep of all sectors | `SEARCH` at high altitude band (wide footprint, lower p_detect) | Scouts |
| 2 | Sector sweep of prioritised sectors | `SEARCH` at low band; sector priority from belief mass | Scouts |
| 3 | Primary rescue at viable sites | `VERIFY`, then `DELIVER` | Rover, cargo drone, low-band scout |
| 4–5 | Out of scope | — | Human USAR teams (structural work) |

This gives the decomposition an external reference: a judge who asks "why these phases?" gets "because that is how INSARAG-classified teams sequence a search."

#### 6.2.2 Pipeline

1. **LLM call.** System prompt contains the `MissionSpec` JSON Schema and four worked examples; temperature 0; JSON output mode where the provider offers one.
2. **Validation.** Pydantic parse; reject unknown sectors, unknown task kinds, and ASR levels > 3. On failure, one repair call with the validation error; on a second failure, fall back.
3. **Grammar fallback.** A deterministic parser: sector lists (`sectors? ([A-Z])(?:, ?([A-Z]))*(?: and ([A-Z]))?`), verbs (search / scan / assess / sweep → ASR 1–2; deliver / drop / supply + item → ASR 3 spawn rule), constraints (keep in contact / maintain comms → `maintain_link_all`; avoid smoke / fire → `avoid: plume`). Unparsed spans are highlighted in the UI for the operator.
4. **Cache.** Key = SHA-256(normalised objective ‖ map digest ‖ DSL version). Demo missions are pre-cached; the demo runs with the LLM unreachable.
5. **Operator confirmation.** The specification is rendered as a phase list on screen; nothing launches until the operator confirms.

#### 6.2.3 Measured, not claimed

A held-out set of 40 objectives written by two teammates who do not work on W1, paraphrasing the demo intents and a few out-of-scope requests. Metric: field-level exact match against hand-written specifications. Targets: LLM path ≥ 90 %, grammar fallback ≥ 70 % on in-scope phrasings, 100 % refusal of out-of-scope requests (e.g., anything resembling targeting people) `[TARGET]`.

#### 6.2.4 Failure modes and degradation

Ambiguity ("search the area near the school") → the parser flags the unresolved span and the operator picks a sector on the map. LLM unavailable → grammar fallback, stated in the run manifest. The LLM never touches allocation, routing, risk or explanations.

### 6.3 W2 — Allocation, Routing and Search

**Purpose.** O2, D2: decide who does what, in which order, by which route, and where to look. **Inputs.** `MissionSpec`, `BeliefState`, agent states. **Outputs.** Assigned task queues and routes. **Time** run.

#### 6.3.1 Task generation

Sectors from the spec are partitioned into sub-sectors of ≤ 120 cells so that one scout can sweep one in a few minutes. One `SEARCH` task per sub-sector per ASR phase. `VERIFY` and `DELIVER` tasks are spawned by detections (§6.3.4). A `RELAY` task is spawned by W3 whenever a `maintain_link_all` constraint is at risk. `RTB` is implicit at the end of every queue.

#### 6.3.2 One currency: expected survival-weighted aid (fix for IA-01)

The value of reaching survivor *s* at time *t*:

```latex
V_s(t) = p_{\text{real}}(s)\; w_{u(s)}\; e^{-t/\tau_{u(s)}}
```

with triage weights `w` = 3 / 2 / 1 and time constants `τ` = 20 / 60 / 180 min for critical / serious / stable `[POLICY defaults]`. **This is a planning priority model chosen by the operator, not a medical survival estimate**, and the slide says so. A `VERIFY` task's value is the expected value of the `DELIVER` it unlocks, averaged over the urgency prior. A `SEARCH` sub-sector's value is the expected aid from the detections it would produce: Σ over its cells of `P_i · p_detect · E_u[w_u e^{−(t+δ)/τ_u}]`, where δ is the typical verify-and-deliver delay. A plan's **ESA** is the sum of task values at their predicted completion times.

Battery, payload and capability are **constraints**, never cost terms. Risk to agents is **a separate outcome** evaluated by Foresight (§6.5), never added to ESA — that exchange rate is a human's to set.

#### 6.3.3 Regret auction with cheapest insertion (fix for IA-02)

```
open ← unassigned tasks whose dependencies are met or assigned
while open not empty:
    for each task t in open:
        for each agent a:
            if not feasible(a, t): continue           # capability, payload, battery, shield pre-check
            best_pos[a,t], loss[a,t] ← cheapest insertion of t into a.route
                                         # loss = ESA lost by delaying a's later tasks − value of t
        b1[t], b2[t] ← best and second-best loss over agents (b2 = +∞ if one bidder)
    if no feasible (a, t): break                       # leftovers go to W4 (shedding / escalation)
    t* ← argmax_t (b2[t] − b1[t])                     # regret: the task we'd most regret misplacing
    a* ← argmin_a loss[a, t*]
    insert t* into a*.route at best_pos[a*, t*]; remove t* from open
```

Travel times come from per-class distance maps (multi-source Dijkstra from each task location, recomputed when the map changes), so an insertion test is a table lookup. Cost per full auction: tasks T ≈ 30, agents A = 5 → < 50 ms `[ESTIMATE]`. Reference: Koenig et al. 2006 (sequential single-item auctions); Lagoudakis et al. 2005 (auction-based multi-robot routing); Gerkey & Matarić 2004 (taxonomy).

**Feasibility** is a hard gate: required capabilities ⊆ agent capabilities; payload fits; along the insertion route the battery never falls below `reserve_required` (§6.4.2); every route cell is traversable for the agent's class and outside the forecast no-fly mask at its predicted arrival time.

#### 6.3.4 Bayesian search map (fix for IA-04)

Each cell holds `P_i`, the probability it contains an unfound survivor. For a scan of cell *i* with detection probability `p_d` and false-alarm probability `p_fa`:

```latex
\text{no detection: } P_i' = \frac{P_i(1-p_d)}{1 - P_i\,p_d} \qquad
\text{detection: } P_i' = \frac{p_d P_i}{p_d P_i + p_{fa}(1-P_i)}
```

A detection with posterior ≥ 0.25 spawns `VERIFY` (P2); a verification that lifts the posterior to ≥ 0.9 confirms a survivor and spawns `DELIVER` (P1); a verification that drops it below 0.05 closes the detection as a false alarm `[POLICY defaults]`. Because false alarms exist, a fast cargo drone is not committed to every heat signature — the rover or a low pass verifies first, unless Foresight shows verifying costs more expected aid than it saves. References: Stone (1975), *Theory of Optimal Search*; Bourgault, Furukawa & Durrant-Whyte (2003), Bayesian search for a lost target.

Within a sub-sector a scout flies a boustrophedon (back-and-forth) sweep at its assigned band; sub-sectors are ordered by their remaining belief mass, so the swarm searches where survivors are most likely first.

#### 6.3.5 Routing and separation

A\* (8-connected, octile heuristic) per traversability class; edge cost = distance × (1 + α · forecast hazard at predicted arrival) with α = 4 for drones `[ASSUMPTION]`, hard block at `h ≥ 0.5`. Drones are assigned fixed altitude bands (relay 4, scouts 2–3, cargo 1); scouts switch between bands only when changing ASR phase, and the shield enforces separation (fix for IA-13). With one ground agent, ground conflicts cannot occur; cooperative space-time A\* (Silver 2005) is the declared method for multi-rover extensions (Could).

#### 6.3.6 Failure modes

Greedy auctions are not optimal; the gap is measured against OR-Tools (B3) rather than assumed small. A task with no feasible bidder is never silently dropped — it goes to W4, which either sheds it (and says so) or escalates.

### 6.4 W3 — Communications

**Purpose.** MP-4, O4: model who can talk to whom, keep the plan correct when agents go silent, place the relay, and choose what to send. **Time** run.

#### 6.4.1 Radio graph

Nodes: base, relay, agents. Edge if distance ≤ the smaller of the two radio ranges (disk model — declared optimistic). BFS from base each tick marks agents `connected`. Line-of-sight attenuation (range × 0.6 per building cell crossed on the Bresenham line) is a Could-tier refinement.

#### 6.4.2 Energy and computed reserve (fix for IA-07)

Drain per second = `d₀(type) · (1 + κ · payload) · wind multiplier`. The reserve is a procedure, not a constant:

```latex
\text{reserve}_a = E_{\text{to charger}}\big(\text{end of route}_a\big)\,\big(1 + 2\,\mathrm{cv}_a\big)
```

where `E_to_charger` comes from the per-class distance-to-charger map and `cv_a` is the drain-rate coefficient of variation used in Foresight — a two-sigma margin on the trip home from wherever the agent's route ends.

#### 6.4.3 Leases and reconciliation (fix for IA-05)

When a task is assigned, its lease expires at `t_assign + ETA(a, task) · (1 + 2 cv_a) + 30 s`. While the agent is silent and the lease is valid, the task is `presumed_executing`: it is not re-auctioned, and Foresight models the agent along its predicted route. On expiry without contact, the task is released (`LEASE_EXPIRE` record) and the agent is marked `unknown`. On reconnect, the agent uploads its completed tasks and buffered observations; if two agents completed the same task, the first completion stands and the duplicate is counted (the "duplicate work" metric, §10). **Onboard fallback** (simulated agent behaviour, and the rule a real autopilot would run): finish the queue; return to the charger when the battery reaches `reserve_required`; return if silent for 3 × the lease duration.

#### 6.4.4 Relay placement

Candidate positions: every third cell of the relay's reachable set. For each candidate *c*, score = the number of (agent, time) pairs — agents' predicted positions sampled every 30 s over the next 5 minutes — that would be connected to base with the relay at *c*. Take the best; break ties by relay travel time. ≈ 200 candidates × 5 agents × 10 samples = 10⁴ small BFS checks, < 20 ms `[ESTIMATE]`. Recomputed on `COMMS_LOST`, on any plan switch, and every 60 s.

#### 6.4.5 Message prioritisation

Each tick the base link carries at most **B** messages (B = 3 `[ASSUMPTION — scenario parameter]`). Telemetry is coalesced (only the latest position per agent is kept). Decision-relevant messages (`DETECTION`, `HAZARD`, `BLOCKAGE`, `BATTERY_ANOMALY`, `TASK_DONE`) are ordered by **value of information from Foresight** (§6.5.6) when the queue exceeds B (Should), otherwise by a static type table (Must), plus an ageing term (+0.01 per second waited) so nothing starves.

### 6.5 W4 — Foresight ★ (the USP)

**Purpose.** MP-3, MP-4, D4: forecast candidate plans through the swarm's uncertainty, and use that one forecast to decide re-planning, communication priority, task shedding and escalation. **Inputs.** `BeliefState`, agent states, candidate plans from W2. **Outputs.** `Forecast` (§5.3.5), classification FACT / VALUE / POLICY / MISSION-AT-RISK. **Time** run. **No training, no learned model** — Monte Carlo over a stated stochastic model.

#### 6.5.1 What is sampled — from belief, never from truth

| Uncertain quantity | Sampling model |
|---|---|
| Unfound survivors | Bernoulli per cell from the search map, restricted to the 200 highest-mass cells for speed |
| Detections not yet verified | Real with probability = posterior; urgency from the prior |
| Future scans | Detections and false alarms at the agent's `p_d`, `p_fa` |
| Battery drain | Multiplier per agent per rollout ~ LogNormal(0, cv_a) |
| Plume | Growth rate × U(0.8, 1.2); wind direction random walk |
| Radio | Disk model + per-link dropout episodes |
| Agent faults | Constant hazard per agent-minute |
| Disconnected agents | Position along predicted route with timing noise |

The Foresight model is deliberately **simpler than the simulator** in three declared ways (linear drain, no line-of-sight, plume growth as a scalar), so that it cannot score itself against a copy of the truth.

#### 6.5.2 Rollouts

N = 64 rollouts, horizon H = 600 s, step 5 s, all agents and all rollouts advanced together as NumPy arrays of shape (N, A). Each rollout executes the candidate plan open-loop with the onboard fallback rules (return at reserve, skip a blocked task). Per rollout, record: ESA achieved (values at actual completion times, using the sampled survivors), whether any agent was lost (battery exhausted away from a charger, or entered `h ≥ 0.8` `[ASSUMPTION]`), and whether any P1 task missed its deadline (its value has decayed past `e⁻¹`).

**Common random numbers.** Random draws are pre-generated as tensors indexed by (rollout, agent, step) and shared by every candidate plan, so a difference between two plans is caused by the plans rather than by luck.

**Time-to-infeasibility (TTI).** For the current plan, the first time at which fewer than half of the rollouts can still complete every P1 commitment. Shown on the KPI bar as "mission achievable for ~6 min at current trends".

#### 6.5.3 Candidate plans (k ≤ 5)

1. Current plan. 2. Local repair (re-auction only the tasks touched by the event). 3. Full re-solve from the current state. 4. **Veto variants**: for each agent whose route crosses forecast hazard, or whose loss probability exceeds 0.05, a re-solve with that agent barred from the hazard. 5. **Shedding variant** (fix for IA-14): drop the lowest-value P3 and then P2 tasks until all P1 commitments are feasible. A variant that sheds a P1 task is generated only when no other candidate keeps all P1 tasks feasible, and it is always escalated.

#### 6.5.4 The fact/value classification

For each pair of candidates, compute paired differences across the 64 shared rollouts on three outcomes — ESA, P(agent loss), P(P1 failure) — with 95 % bootstrap intervals (1,000 resamples). Candidate X **dominates** Y if it is no worse on all three (interval bound within tolerance ε = 0.01 `[POLICY]`) and better on at least one (interval excludes zero).

```
cands ← generate_candidates(state)                    # §6.5.3
F ← forecast(cands, crn)                              # N=64 rollouts each
best_p1 ← min over c of F[c].p_p1_fail
if best_p1 > policy.p1_fail_floor:          → MISSION_AT_RISK   (escalate; show shedding option)
D ← candidates that dominate current
if D non-empty and one d ∈ D dominates all others in D:
                                            → FACT: switch to d (autonomous, logged)
front ← Pareto-non-dominated candidates (on the 3 outcomes)
if |front| ≥ 2 and members differ with intervals excluding 0 on different outcomes:
    if policy.exchange_rate is set:         → POLICY: choose by commander's rate (logged, cites policy)
    else:                                   → VALUE: escalate with the front
else:                                       → FACT: keep current ("no candidate is credibly better")
```

The last branch matters as much as the others: when the evidence cannot separate the plans, the swarm does not churn and does not bother the human; it keeps its plan and says why.

#### 6.5.5 Why this escalation rule

v1.0 escalated when a confidence number was low. A low number does not mean a human can do better: if every option is bad and one is clearly least bad, asking a human only adds delay. Humans add value in two situations — when the choice depends on **what we are willing to trade** (a minute of a critical survivor's time against a 15-point risk of losing the cargo drone), and when **the mission as committed is failing** and something must be given up. Those are exactly the two escalation triggers. Everything else is a question of fact that the swarm can settle with evidence, and does.

#### 6.5.6 Value of information for messages

For each of the top 5 queued decision-relevant messages (by type prior): update a copy of the belief with the message, re-run the auction to get the plan that belief implies, and forecast both that plan and the current one under the updated belief with common random numbers. `VoI(m)` = the mean ESA difference. Send in VoI order. Computed only when the queue exceeds B, so the cost (≈ 5 auctions + 10 rollout batches ≈ 300 ms `[ESTIMATE]`) is paid only when bandwidth is actually scarce. Closest prior work: ConTaCT (Unhelkar & Shah, AAAI 2016) decides *whether* agents communicate in time-critical collaborative tasks; here the same forecast that drives planning also ranks a shared, rate-limited link.

#### 6.5.7 Cost and budget

One rollout batch (N = 64, 120 steps, A = 5) ≈ 15 ms in NumPy `[ESTIMATE]`; an epoch with 5 candidates and their auctions ≈ 150 ms. Epochs run on every event and every 30 s of simulated time; at 10× speed that is every 3 s of wall time. If an epoch exceeds a 500 ms budget, N halves to 32 for that epoch and the record states it (wider intervals, fewer FACT switches — the conservative direction).

#### 6.5.8 Failure modes

Foresight is only as good as its stochastic model. If the real world is more variable than the model (stronger winds, faster drain), forecasts are overconfident. Mitigations: the deliberately simplified model (§6.5.1), the misspecification experiment (§13.2), and the safety shield, which does not depend on Foresight at all.

### 6.6 W5 — Safety Shield and Escalation ★

**Purpose.** O4, D4: guarantee hard limits regardless of the planner, and run the human interface for escalations. **Time** run.

#### 6.6.1 Shield invariants (fix for IA-11)

Checked every tick for every agent over the next 60 s of its committed route, by a module of ≈ 300 lines that imports nothing from W2 or W4:

| # | Invariant | Override on violation |
|---|---|---|
| I1 | No cell with current or 60 s-forecast hazard ≥ 0.5 | Drone: HOLD at last safe waypoint · Rover: stop · request re-plan |
| I2 | Battery ≥ `reserve_required` at every point of the route | Return to charger now |
| I3 | Inside the geofence | HOLD, request re-plan |
| I4 | Drones within 1 cell of each other are in different altitude bands | Lower-priority drone holds |
| I5 | Every assigned task is within the agent's capabilities | Reject assignment |
| I6 | Ground agents only on traversable cells | Stop, request re-plan |

Operator commands pass through the shield too: an operator forcing a drone through the plume is refused and the refusal is logged (`SHIELD_OVERRIDE`, classification `SAFETY`). The invariants are tested with Hypothesis over randomly generated maps, plans and events (§10.6).

#### 6.6.2 Escalation manager (fix for IA-15)

- **Queue** ordered by deadline (time until the default would execute) and stakes (Σ ESA at risk).
- **Rate limit**: at most one dialog per 60 s of simulated time; concurrent VALUE decisions are batched into one dialog.
- **Default on timeout** `[POLICY]`: the option with the lowest P(agent loss) among those with P(P1 failure) ≤ the floor; if none, the lowest P(P1 failure). Logged as `DEFAULT_ON_TIMEOUT`.
- **Dialog content**: a Pareto plot (x = expected aid, y = agent-loss risk, 95 % interval whiskers), one line per option describing what it trades, the time remaining, and the option the default rule would pick.
- **Metrics**: escalations per mission-hour (target ≤ 6 `[TARGET]`), operator response time, share of escalations that were VALUE versus MISSION-AT-RISK.

### 6.7 W6 — Explanation and Accountability

**Purpose.** D4: an explanation for every major decision, and an unalterable record. **Time** run. **No LLM.**

#### 6.7.1 Contrastive explanations

One template per decision kind, filled only from the `DecisionRecord` and its `Forecast`. Examples:

- FACT: *"Switched to plan B: better on every count — +0.31 expected aid (95 % CI 0.18–0.41), agent risk 3 % → 2 %, rescue-failure risk 22 % → 8 %."*
- VALUE: *"Two plans trade differently. A reaches S1 9 minutes sooner but puts Cargo-1 at 19 % risk in the smoke edge; B uses Rover-1 on the long road with 2 % risk. This is a judgement about acceptable risk, so it is yours."*
- SAFETY: *"Refused: route enters forecast smoke (hazard 0.62 in 40 s)."*

Each explanation names the runner-up ("why not") and its deciding margin. Reference for the contrastive form: Krarup et al. (2021, JAIR), contrastive explanations of plans.

#### 6.7.2 Fidelity test

Every number in a generated explanation is parsed back and compared with the record it came from; CI fails on any mismatch over 1,000 generated records. This is why v2.0 does not let an LLM rephrase explanations (RD-3): a fluent explanation that disagrees with the decision is worse than none.

#### 6.7.3 Flight recorder and replay

The decision log is JSON Lines; each record is serialised canonically (sorted keys, no whitespace) and hashed as `SHA-256(prev_hash ‖ record)`. At mission end the final hash is signed with Ed25519; `samanvay verify-log` re-checks every link and the signature. **Replay**: scenario + seed + the event log (including operator choices) reproduces the run exactly; CI checks that replay yields an identical log digest.

#### 6.7.4 After-action report

Generated at mission end in the console and printable to PDF: timeline of events by origin, every decision with its explanation, every escalation with the operator's choice and response time, shield interventions, and final metrics against the baselines run on the same seed.

---

## 7. Novel contributions and the USP

### 7.1 Applied / Adapted / Invented

| Component | Status | Basis |
|---|---|---|
| A\* routing, per-class traversability | **Applied** | Hart, Nilsson & Raphael 1968 |
| Sequential single-item auction with regret and cheapest insertion | **Applied** | Koenig et al. 2006; Lagoudakis et al. 2005 |
| Bayesian search map with detection and false-alarm rates | **Applied** | Stone 1975; Bourgault, Furukawa & Durrant-Whyte 2003 |
| Disk-model connectivity, BFS | **Applied** | Textbook |
| Relay placement by predicted-connectivity score | **Adapted** | Relay placement is studied widely; scoring candidates against agents' *forecast* routes rather than current positions is our design choice, not a claimed invention |
| Lease-based task ownership under disconnection | **Adapted** | Leases are a classic distributed-systems mechanism (Gray & Cheriton 1989); applying them with expiry derived from the agent's own predicted completion is ours |
| Safety shield over a planner | **Applied** | Simplex (Sha 2001); shielding (Alshiekh et al. 2018) |
| INSARAG-phased mission DSL from natural language | **Adapted** | INSARAG ASR levels are doctrine; using them as the grammar of an LLM-produced, schema-validated mission spec is our application |
| Survival-weighted aid as a single planning currency | **Adapted** | Time-discounted rewards are standard; the urgency-class decay as an operator-set triage policy is our framing |
| Value of information for a rate-limited shared link | **Adapted** | ConTaCT (Unhelkar & Shah 2016) and the VoI literature; computing it with the same forecast that drives planning is ours |
| Contrastive explanations with a fidelity test | **Adapted** | Krarup et al. 2021 for the contrastive form; the mechanical fidelity test is engineering |
| Hash-chained, signed decision log with replay | **Applied** (engineering) | SHA-256, Ed25519 (RFC 8032) |
| **Fact/value-separating autonomy: one belief-sampled forecast that drives re-planning, communication priority, task shedding and human escalation, escalating exactly on statistically separated Pareto trade-offs and committed-mission failure** | **Invented** — as a method of deciding *when* a swarm should act alone; each ingredient is published | See §7.3. Borderline honestly stated: a reviewer could call it Adapted multi-objective decision support. We claim the coupling and the escalation criterion, not the ingredients. |
| OR-Tools baseline, OSM import, React console | **Engineering** | Differentiators in quality of evidence and demo, never the USP |

### 7.2 The four falsification tests, applied

| Contribution | Deletion (EL-05 still satisfied without it?) | Convergence (would a competent team arrive here?) | Library (weekend assembly?) | Non-obviousness | Verdict |
|---|---|---|---|---|---|
| Fact/value autonomy (W4 + W5) | **No** — MP-4 and D4 require escalation "when autonomous confidence is insufficient" and a "mission-feasibility/risk assessment"; without W4 these are met only by an undefined confidence threshold, which v1.0 showed is not a mechanism | **No** — the obvious reading of the PS is "escalate when confidence is low"; reframing escalation as a value-versus-fact question is a different idea | **No** — no package provides belief-sampled paired forecasts tied to a dominance-based escalation rule | **Yes** — "it escalates when the options trade different goods, not when it is unsure" is the reaction we want, and it inverts the expected design | **USP** |
| Lease protocol | No (comms-loss handling is required, some mechanism is needed) | Partly | Partly | Moderate | Differentiator — fixes a duplicate-work defect most designs have |
| Safety shield | Yes (PS does not demand it) | Partly | Partly | Moderate | Differentiator — answers "what if your planner is wrong?" |
| Bayesian search with false alarms | Yes | Partly | Yes | Low | Correctly applied, makes the demo honest |
| INSARAG-phased DSL | Yes | No | Partly | Moderate | Differentiator (domain credibility) |
| VoI message ranking | No (MP-4 "which observations are important enough to transmit") | Partly (static priorities are obvious; forecast-driven VoI is not) | No | Moderate | Differentiator; Should tier |
| OR-Tools baseline + held-out families | Yes | No (most teams compare to nothing or a strawman) | Yes | Low | Evidence quality, not novelty |

### 7.3 The USP

**One sentence (title slide).** *SAMANVAY is a swarm planner that can tell a question of fact from a question of value: it forecasts every candidate plan through its own uncertainty, acts alone when one plan is better on every count, and hands the human only the decisions that trade one good against another.*

**The defence.** A reviewer says: "auctions are Koenig 2006, A\* is 1968, Monte Carlo rollouts are textbook, adjustable autonomy is Scerri, Pynadath & Tambe 2002 — this is application." Correct for every ingredient, and §7.1 says so. What is not published is the decision rule and its coupling. Adjustable-autonomy work (Scerri et al. 2002, JAIR) decides whether to transfer control by comparing expected utilities — which presupposes a single utility, i.e., that the exchange rate between agent risk and mission value is already known; under that assumption there is never a value question to ask. Multi-objective planning (Roijers et al. 2013, JAIR survey) computes Pareto sets of policies but does not decide, *during execution*, which decisions need a human. Chance-constrained, risk-bounded planning enforces a fixed risk bound rather than recognising when the bound itself is the open question. ConTaCT (2016) decides when agents should communicate, but not when to escalate. SAMANVAY's specific, testable claims are: (1) escalation is triggered by **statistically separated Pareto incomparability** across belief-sampled, common-random-number forecasts — not by a low score; (2) the **same forecast** decides re-planning (dominance), communication priority (value of information) and task shedding, so the four behaviours cannot contradict each other; (3) when evidence cannot separate plans, the system neither churns nor escalates — "insufficient evidence to change" is a first-class outcome.

**The falsification.** Evaluate three policies on held-out families F2–F4 with simulated operators who hold one of three declared value profiles (cautious, balanced, aggressive — each an exchange rate between agent-loss risk and aid). Define:

- **Escalation precision** — the share of escalations where the three profiles disagree on the best option (the question genuinely was one of value).
- **Value-misaligned autonomy** — the share of autonomous decisions where at least one profile, evaluated in hindsight on the true world from the same state, would have chosen a different option with a material margin (> 5 % of ESA or > 5 points of agent-loss risk).

The claim is **false** if Foresight's escalation precision is not higher than a confidence-threshold baseline (v1.0's rule) and a single-utility baseline (adjustable-autonomy style), or if it achieves precision only by escalating far more often. It **holds** if escalation precision ≥ 0.8 and value-misaligned autonomy ≤ 5 %, against ≤ 0.5 and ≥ 15 % for the threshold baseline, with ESA no worse than either baseline (paired interval) and escalations per mission-hour ≤ 6 `[TARGET — pre-registered here, measured in §10]`.

**The literature gap.** *MRTA* methods (auctions, CBBA, VRP solvers) optimise a single objective and stop. *Adjustable autonomy* transfers control using a single expected utility and stops. *Multi-objective planning* computes trade-off sets offline and stops. *Communication-policy* work decides when agents talk and stops. *Explainable planning* explains a chosen plan and stops. We found no method that uses one belief-sampled forecast to decide re-planning, communication priority and shedding, **and** classifies each decision as factual (dominance), value-laden (separated incomparability) or mission-at-risk, escalating only the latter two. `[VERIFY: one further literature pass on "human-on-the-loop escalation multi-objective" before the PPT gate; if prior work is found, the row is relabelled Adapted and §7.3 is rewritten — the design does not change.]`

### 7.4 Each addition against the six constraints

| Addition | What it does | Not redundant because | How built | Person-hours | Proving metric | Adds to the pitch |
|---|---|---|---|---|---|---|
| W4 Foresight + fact/value rule | Forecasts plans; drives switch, shed, escalate | Replaces v1.0's undefined confidence score | NumPy rollouts, CRN tensors, bootstrap | 14 | Escalation precision, misaligned autonomy (§7.3) | The USP and the climax of the demo |
| Safety shield | Hard limits independent of the planner | Nothing in v1.0 bounded planner errors | Pure-Python checks, Hypothesis tests | 4 | 0 invariant violations in 1,000 randomised runs | "Our planner can be wrong; our swarm still can't hit the smoke" |
| Leases | Correct handling of silent agents | v1.0 duplicated work under comms loss | State machine in W3 | 4 | Duplicate-work count vs B1/B2 | Handles the PS's "rover loses communication" correctly |
| Bayesian search with false alarms | Honest detection uncertainty | v1.0 had only misses | 2 update formulas, belief grid | 4 | False-alarm verification cost vs survivors found | A false alarm is caught live in the demo |
| INSARAG-phased DSL | Doctrine-shaped missions | v1.0 had free-form tasks | Schema + prompt + grammar | 6 | Parse accuracy on 40 held-out objectives | Domain credibility with any responder on the panel |
| OSM real map | Real streets near the venue | Synthetic grid in v1.0 | osmnx + Shapely, cached | 4 | — (visual) | "This is Vile Parle, rasterised from OpenStreetMap" |
| OR-Tools baseline + held-out families | Strong comparison, no self-grading | v1.0 compared to a strawman | OR-Tools VRP re-solve at each epoch | 6 | Paired ESA difference with CI | Evidence a judge can trust |

---

## 8. Interface architecture decision

### 8.1 Constraints

1. Runs on one laptop with no internet at demo time. 2. Renders a 3,072-cell map with five moving agents, overlays and charts smoothly on a projector. 3. Buildable by the team in the time with skills it has (Python, JavaScript, React). 4. Reads as a mission-control console, not a dashboard template.

Unlike a security tool, EL-05 imposes no constraint against a local listener; the server binds to 127.0.0.1 and exposes nothing beyond the laptop.

### 8.2 The comparison (1 = worst, 5 = best)

| Option | Offline reliability | Map + animation capability | Charts (fan, Pareto) | Team skill fit | Build speed | Mission-console legibility | Total |
|---|---|---|---|---|---|---|---|
| **React + Canvas 2D, served by FastAPI** | 5 | 4 | 5 | 5 | 5 | 4 | **28** |
| React + PixiJS (WebGL) | 5 | 5 | 5 | 3 | 3 | 5 | 26 |
| React + MapLibre / deck.gl | 2 (tiles) | 5 | 5 | 3 | 3 | 5 | 23 |
| PySide6 + pyqtgraph (native) | 5 | 4 | 3 | 2 | 2 | 5 | 21 |
| Streamlit / Dash | 4 | 2 (re-render per tick) | 4 | 4 | 4 | 2 | 20 |
| Pygame | 5 | 4 | 1 | 3 | 3 | 2 | 18 |
| Unity / Godot 3D | 5 | 5 | 2 | 1 | 1 | 4 | 18 |

**Decision: React + Canvas 2D, built to static files and served by the same Python process.** PixiJS is the upgrade path if Canvas frame rate becomes a problem — the drawing code is isolated behind one `MapRenderer` interface so the swap touches one file.

**Sacrificed, honestly:** 3D terrain and altitude visualisation (altitude is shown as band badges); real map tiles (the OSM map is drawn as our own vector layers, which also looks more like a tactical display); a desktop-native feel.

### 8.3 Console artifacts — implementation

| # | Artifact | Implementation | Interaction | Data source |
|---|---|---|---|---|
| C1 | Mission map | One `<canvas>`; layers drawn in order: terrain, belief heat-map (alpha-blended), plume (current solid, forecast dashed outline), radio links (lines, grey when broken), routes (dashed per agent colour), **re-plan ghost** (old route faded for 3 s), agents (icons with band badge), event ripples | Layer toggles; click agent → card focus; click cell → belief value tooltip | `TICK`, `SNAPSHOT` |
| C2 | Agent cards | React components: battery bar with reserve marker, link state, lease countdown when silent, current task, queue | Click → highlight route | `TICK` |
| C3 | ★ Foresight fan chart | Recharts: per candidate, ESA distribution as box/violin; TTI countdown in the KPI bar | Hover → paired difference and interval vs current | `FORECAST` |
| C4 | Decision log | Virtualised list; colour tag FACT (green), VALUE (blue), POLICY (purple), SAFETY (red); "why not?" expands runner-up | Click → highlight affected agents on C1 | `DECISION` |
| C5 | ★ Escalation dialog | Modal with D3-scaled SVG Pareto plot (x aid, y agent-loss risk, CI whiskers), option cards, countdown, default marked | Choose option; response sent; dialog logs response time | `ESCALATION` |
| C6 | Comms queue | Horizontal bars of VoI per queued message; "sent this tick" highlighted | Hover → what the message would change | `COMMS` |
| C7 | After-action report | Route-level page: timeline, decision table, metrics vs baselines (Recharts bar with interval whiskers), log-verification status | Print to PDF | REST `/report/{run}` |

The UI never computes a decision. Everything it shows exists in the decision log, so the console failing never loses the record.

---

## 9. Tech stack

Versions are pinned to exact numbers in `requirements.lock` and `package-lock.json` at the schema freeze; the majors below are the design assumption `[VERIFY at freeze]`.

| Layer | Library | Version (major) | Role and justification |
|---|---|---|---|
| Language | Python | 3.11 | Team language; wheels for every dependency |
| Arrays | NumPy | 1.26 or 2.x | Vectorised rollouts and grid operations |
| Statistics | SciPy | 1.x | Wilcoxon, bootstrap helpers, distributions |
| Server | FastAPI + Uvicorn | 0.1xx / 0.3x | One process, WebSocket + static files, bound to 127.0.0.1 |
| Validation | Pydantic | 2.x | Schemas for messages, LLM output, files |
| Map import (build) | osmnx, Shapely | 2.x / 2.x | OpenStreetMap to grid, cached |
| Baseline (eval) | ortools | 9.x | B3 optimiser baseline only |
| Crypto | `cryptography` (Ed25519), `hashlib` | 4x | Flight recorder |
| LLM client | provider SDK or `httpx` | — | Mission parsing only; cached; optional at demo time |
| Tests | pytest, Hypothesis, import-linter | 8.x / 6.x / 2.x | Unit, property-based invariants, truth/belief firewall |
| Front end | React, Vite | 18 / 5 | Console, built to static files |
| Charts | Recharts, d3-scale | 2.x / 4.x | Fan chart, Pareto plot, evidence charts |
| Styling | Tailwind CSS | 3.x | Dark mission-console theme, projector contrast |
| Motion | Framer Motion | 11.x | Dialog and log transitions only |

**Run path.** `pip install -r requirements.lock && npm ci && npm run build` once; then `python -m samanvay serve` serves everything from one process. `samanvay doctor --offline` runs a full mission with outbound sockets refused. The demo laptops carry the built front end, the cached OSM map, the cached LLM responses and the scenario files, so nothing is downloaded on the day.

---

## 10. Evaluation methodology

Every number that appears in the deck comes from `samanvay evaluate`, which writes to one registry (`registry.jsonl`) with the scenario id, seed, policy, metric, value and code commit. The deck is built from the registry, never typed.

### 10.1 Metrics — computation and targets

| Metric | Computation | Target `[TARGET]` |
|---|---|---|
| ESA | Σ over survivors aided of `p_real · w_u · e^{−t/τ_u}` using **true** survivors and true aid times | Paired gain over B1 with 95 % CI > 0 on every family |
| Survivors aided in time | Share of true survivors aided before `τ_u` | Report per urgency class |
| Time to first aid | Minutes from launch to first `DELIVER` completion | Report |
| Coverage | Share of building and rubble cells scanned at least once by end of horizon | Report |
| P1 failures | Committed P1 tasks that missed their deadline | ≤ B3's rate |
| Agent losses | Agents with exhausted battery away from a charger or inside `h ≥ 0.8` | **0** in all runs with the shield on |
| Duplicate work | Tasks completed by two agents | Lower than B1 and B2 (lease effect) |
| Escalation precision | §7.3 | ≥ 0.8 |
| Value-misaligned autonomy | §7.3 | ≤ 5 % |
| Escalations per mission-hour | Count / simulated hours | ≤ 6 |
| Re-plan latency | Wall time from event to new plan, p50 / p95 | p95 < 500 ms |
| Plan churn | Reassignments per agent per 10 min | Report; lower than B1 |
| Crash-free rate | Runs completing without exception in the randomised suite | 100 % of 1,000 |
| Explanation fidelity | Numbers in explanations matching records | 100 % |

### 10.2 Baselines (fix for IA-03)

| Id | Policy | Why it is here |
|---|---|---|
| B0 | Static: nearest capable agent at launch, no re-planning | Lower bound |
| B1 | Nearest capable agent + re-plan on every event | What most teams will build |
| B2 | v1.0 design: auction + event-triggered local repair + fixed priorities + confidence-threshold escalation | Shows what v2.0 changed |
| B3 | OR-Tools vehicle-routing re-solve at every epoch, given the same belief, maximising ESA proxy (prize-collecting VRP with time-decayed prizes, 1 s time limit) | A strong optimiser; tells us whether the auction loses much quality |
| **S** | SAMANVAY v2.0 | — |

Escalation-policy comparisons for the USP (§7.3) use two further variants of S with W4's classifier replaced: **E-thr** (escalate when a min-of-scores confidence < 0.5, v1.0) and **E-util** (single weighted utility with the balanced profile's exchange rate; escalate when the best option's utility margin over the runner-up is below its interval width — adjustable-autonomy style).

### 10.3 Protocol

1. **Tune** only on F1 seeds 0–49 (cost-model constants, epoch period, rollout count).
2. **Freeze**: tag `eval-freeze` in git; the registry rejects held-out runs from any other commit.
3. **Test** on F1 seeds 1000–1099 and F2, F3, F4 seeds 2000–2099 (100 seeds each; F2–F4 never seen during tuning).
4. **Pair** by seed: every policy runs on the same scenarios with the same truth random stream.
5. **Report** per family: mean paired difference with 95 % bootstrap interval; Wilcoxon signed-rank p-values with Holm correction across the four baselines. Every row is printed, including families where S does not win.

### 10.4 External sanity lane — CVRPLIB (Could)

The auction is our core heuristic, and our scenarios are our own. To show it behaves sensibly on a benchmark we did not make, run it as a static capacitated vehicle-routing heuristic (vehicles = agents with capacity, customers = tasks with demand, cost = distance) on the Augerat Set A instances from CVRPLIB, and report the percentage gap to the published best-known solutions alongside OR-Tools' gap on the same instances `[VERIFY: instance set and best-known values at the CVRPLIB site]`. This is not a claim that SAMANVAY is a CVRP solver; it is a calibration of the heuristic against public optima.

### 10.5 USP evaluation — simulated operators

Three operator profiles, each an exchange rate between agent-loss risk and ESA: cautious (one point of agent-loss probability is worth 0.05 ESA), balanced (0.02), aggressive (0.005) `[POLICY — declared for the experiment]`. For every escalation, check whether the profiles disagree on the best option (escalation precision). For every autonomous decision, re-run from the saved state on the true world under each option (hindsight evaluation, 16 truth-world rollouts per option) and check whether any profile would have chosen differently by a material margin (value-misaligned autonomy). Compared for S, E-thr and E-util on F2–F4.

### 10.6 Robustness and safety suite (fix for IA-10)

- **Randomised runs:** 1,000 missions across all families with random seeds and random event injections (every 30–120 s of simulated time, uniform over event types). Pass criteria: no exception, no invariant violation (I1–I6), no agent loss with the shield on, replay digest identical.
- **Property-based tests (Hypothesis):** random maps, routes and hazard fields — the shield must never approve a route that enters `h ≥ 0.5`; the auction must never assign an incapable agent; reserve computation must be monotone in distance.
- **Judge mode** (demo): the judge chooses the seed and injects events; the run is recorded to the registry like any other.

### 10.7 Anti-overfitting mechanisms

1. Tuning on one family, testing on three unseen families.
2. Frozen commit for all held-out numbers.
3. Pre-registered targets in this document, written before any held-out run.
4. A strong baseline (B3), not only strawmen.
5. Foresight's internal model deliberately simpler than the simulator (§6.5.1).
6. Truth/belief firewall enforced in CI (§5.4).
7. All rows reported, including losses.

### 10.8 Generality proof

The `inspection_crawler` plugin (§5.5) is evaluated on F3 (industrial fire) with zero planner changes; F2 (flood) forces a different agent mix to do the work. If SAMANVAY's gains hold on F2–F4, the design is not tuned to one map or one agent roster.

---

## 11. Safety and security architecture

### 11.1 Hazards and controls

| Hazard | Control | Where |
|---|---|---|
| Planner routes an agent into a hazard | Shield I1 (independent of planner), Foresight veto variants | §6.6.1, §6.5.3 |
| Agent stranded with an empty battery | Computed reserve as a feasibility constraint and shield I2; onboard return-at-reserve | §6.4.2, §6.6.1 |
| Two drones in the same airspace | Altitude bands + shield I4 | §6.3.5 |
| Duplicate or abandoned work after comms loss | Leases and reconciliation | §6.4.3 |
| Misread mission | Schema validation + operator confirmation + held-out parse test | §6.2 |
| Operator overloaded by escalations | Rate limit, batching, defaults on timeout | §6.6.2 |
| Explanation contradicts the decision | Template-only explanations + fidelity test | §6.7.2 |
| Record altered after the fact | Hash chain + Ed25519 signature + replay | §6.7.3 |
| Planner "cheats" with ground truth | Truth/belief firewall in CI | §5.4 |

### 11.2 SAMANVAY's own attack surface

- The server binds only to 127.0.0.1 and serves one user on one machine. There is no authentication on the WebSocket because nothing off the laptop can reach it; in deployment the laptop's OS login is the boundary.
- The only outbound call is the optional LLM request at mission entry, which carries the objective text and a map summary (sector names, hazard types) — no imagery, no positions. Demo mode makes no outbound calls.
- Scenario and map files are parsed by Pydantic with size caps; nothing is executed from them.

### 11.3 Command authentication in deployment (design, not built)

A real swarm needs commands that cannot be spoofed. The adapter layer is where this belongs: MAVLink 2 supports message signing, and ROS 2 supports DDS security (SROS2) `[VERIFY: both features and their current status]`. SAMANVAY's planner is unaffected — it hands waypoints to the adapter, and the adapter signs them.

### 11.4 Keys

The flight-recorder signing key is generated per deployment by `samanvay keygen` and held by the mission commander; its public-key fingerprint is printed on every after-action report. A compromised key allows forging logs signed after the compromise; logs already signed and archived remain verifiable.

### 11.5 Trust boundaries (printed in every after-action report)

The simulator (or, in deployment, the agents' own state reports) is trusted to report agent state; the stochastic model in Foresight is trusted to be roughly right, and §13.2 measures what happens when it is not; the operator is trusted with value decisions; nothing else is trusted.

---

## 12. Standards and doctrine alignment

| Framework | What it says that matters here | How SAMANVAY maps | Decision |
|---|---|---|---|
| **INSARAG Guidelines, Vol. III Annex B20 — ASR levels** | USAR operations proceed through wide-area assessment, sector assessment, and primary, secondary and full-coverage search and rescue | Mission DSL phases = ASR 1–3; ASR 4–5 declared human work | **Adopt** (verified against the INSARAG annex) |
| Levels of automation (Parasuraman, Sheridan & Wickens 2000, IEEE SMC-A) | Automation can be set at different levels for information acquisition, analysis, decision and action | FACT decisions: high-level automation with veto; VALUE decisions: system narrows options and the human selects; SAFETY: automatic, cannot be overridden without commander authority | **Adopt as vocabulary** on the architecture slide |
| IEEE 7001-2021, Transparency of Autonomous Systems | Transparency requirements per stakeholder | Decision log, contrastive explanations, after-action report, replay | **Map** `[VERIFY: the standard's stakeholder categories and levels before quoting]` |
| India Drone Rules 2021 / DigitalSky airspace zones | Drone operation is governed by zoned airspace and permissions | Geofence and no-fly layers accept zone polygons; shield I3 enforces them | **Acknowledge** `[VERIFY: current rules and zone definitions]` |
| ASTM F3548-21, UAS Traffic Management interoperability | Strategic deconfliction of operational intents between operators | Altitude bands and committed routes are an operational-intent equivalent within one swarm | **Acknowledge as future integration** `[VERIFY]` |
| MAVLink 2 / ROS 2 | De facto interfaces to drones and robots | `AgentAdapter` implementations are the integration path | **Adopt as the adapter targets** (§19.4) |
| NDMA guidelines on disaster response | National disaster-management doctrine in India | Operating model (§19) assumes NDRF/SDRF USAR teams as users | **Acknowledge** `[VERIFY: relevant guideline documents]` |

---

## 13. Robustness analysis — what we claim and what we refuse to claim

### 13.1 Claims

| Claim | Under what conditions | Evidence |
|---|---|---|
| Safety invariants I1–I6 hold | Always, given correct agent state reports | Shield tests, 1,000-run suite |
| ESA gain over B1 | On the four families, under the stated stochastic model | §10.3 paired intervals |
| Escalation precision and low misaligned autonomy | Under the three declared operator profiles | §10.5 |
| Correct handling of silent agents | Disk-model comms with dropout episodes | Duplicate-work metric |

### 13.2 Model misspecification experiment

Foresight's model is run with deliberately wrong parameters while the simulator keeps the true ones: drain variance × 2, p_detect −20 %, wind speed × 1.5, link dropout × 2. Reported: change in ESA, P1 failures, shield interventions, and misaligned autonomy. Expected pattern: more shield interventions and more escalations, not agent losses — because the shield does not depend on Foresight. If agent losses appear, the shield has a gap and the build is not frozen until it is closed.

### 13.3 What we refuse to claim

- **Adversarial robustness**: GPS spoofing, radio jamming, compromised or lying agents (Byzantine faults). Not modelled; stated.
- **Real-world performance**: all results are in simulation with stated parameters; no claim transfers to real hardware without field trials.
- **Medical outcomes**: ESA is a planning priority model, not a survival prediction.
- **Optimality**: the auction is a heuristic; its gap is measured against B3, not claimed to be zero.
- **Decentralised operation**: the planner is centralised; agents only run fallback rules when disconnected.

---

## 14. Work breakdown

Four seats `[ASSUMPTION: team of 4]`. Work is described by seat, not by person.

| Seat | Owns | Skills needed | Strong ML/statistics? |
|---|---|---|---|
| A — Simulation & evidence | `core` truth side, W0 Scenario Lab, W3 radio/energy/leases, evaluation harness and registry | Python, NumPy | No |
| B — Planning brain | W2 allocation/routing/search, **W4 Foresight**, W5 shield | Python, probability, algorithms | **Yes** — W4's paired statistics and Bayesian search |
| C — Console | All front end, C1–C7 | React, Canvas | No |
| D — Mission, explanation & story | W1 mission understanding, W6 explanation/recorder, baselines B0–B2, PPT, demo script, Q&A | Python, prompt design, presentation | Light |

### 14.1 Dependencies and critical path

```
schemas (all, H0–2) ──► sim tick + map (A) ──► distance maps + A* (B) ──► auction (B) ──┐
                     └► mock TICK stream ──► map canvas (C) ─────────────────────────────┼─► integration ─► Foresight + classifier (B) ─► escalation dialog (C) ─► demo rehearsal
                     └► DSL + grammar (D) ──────────────────────────────────────────────┘
```

**Critical path:** schemas → simulator tick → A\* → auction → integrated map → Foresight → escalation dialog → rehearsal. Everything else hangs off it in parallel.

### 14.2 Single points of failure and mitigations

| SPOF | Mitigation |
|---|---|
| Seat B carries both the planner and Foresight | Seat D implements the shield (W5) and baselines; Foresight's rollout engine is written against the frozen schema so seat A can pair on it; B2 (v1.0 design) is a working fallback planner if Foresight slips |
| Console stalls | C develops against a mock `TICK` stream from hour 2; the after-action report and a recorded replay are fallbacks |
| LLM unavailable | Grammar fallback and cache (§6.2) |
| One laptop fails | Second laptop with the same tagged build, tested before the demo |

### 14.3 Effort ledger (fix for IA-16)

Person-hours (ph). On-site capacity: 4 seats × ~24 productive hours in a 32-hour build ≈ **96 ph** `[ESTIMATE]`.

| Block | Must | Should | Could |
|---|---|---|---|
| Core (schemas, clock, RNG, truth/belief split, adapter, event bus) | 6 | — | — |
| W0 synthetic map, agents, quake/damage/survivors, plume/wind, events, F4 family | 9 | OSM import 4 · F2, F3 families 3 | — |
| W1 DSL, prompt, cache, grammar fallback | 5 | held-out parse test 2 | — |
| W2 distance maps, A\*, ESA values, regret auction, Bayesian search, bands | 16 | — | cooperative A\* 3 |
| W3 radio graph, reserve, leases, relay placement, type-table queue | 12 | VoI ranking 3 | line-of-sight 2 |
| W4 rollouts + CRN, candidates, classifier, TTI | 13 | shedding variant 2 | — |
| W5 shield, escalation manager | 7 | — | — |
| W6 records, templates, hash chain | 5 | replay test 2 · fidelity test 1 | — |
| Console C1, C2, C4, event bar, C3, C5 | 22 | C6 2 · C7 report 3 | PixiJS swap 4 |
| Evaluation harness, B0–B2, held-out runs | 8 | B3 OR-Tools 4 · USP operator-profile study 4 · 1,000-run suite 3 | CVRPLIB lane 3 |
| Integration and rehearsal | 10 | — | — |
| PPT, backup video, Q&A prep | 8 | — | — |
| **Total** | **121** | **33** | **12** |

**The ledger does not close on-site alone.** Must = 121 ph against ≈ 96 ph. Two plans, chosen by the rules `[VERIFY: organisers — is code written before the event permitted?]`:

- **Plan P (pre-building permitted).** Core, W0, W2 and the console skeleton (≈ 55 ph) are built before the event; on-site work is Foresight, W3, W5, W6, integration, evaluation and rehearsal (≈ 65 ph Must + Should as time allows). Comfortable.
- **Plan N (everything on-site).** A reduced Must of ≈ 83 ph: synthetic map only; grammar parser plus cached LLM; Foresight with 3 candidates (current, repair, veto) and no shedding; relay placement by current positions rather than forecast routes; evaluation of S versus B1 and B2 on 30 seeds of F1 plus 30 of F4. Leaves ≈ 13 ph of buffer. The USP survives intact; the evidence base is thinner and the deck says so.

---

## 15. Timeline

Today is 3 October 2026. The gate dates are not yet confirmed `[VERIFY]`, so the timeline is relative.

### 15.1 (a) Before the PPT / idea-submission gate

- This document frozen; schemas drafted (§5.3).
- If prototyping before the event is permitted: a **vertical slice** — synthetic map, five agents moving on A\* routes, the auction assigning search sectors, the canvas map — so the deck carries real screenshots. Real screenshots beat mockups.
- If it is not permitted: the deck uses diagrams and clearly labelled design mockups, never screenshots presented as a working system.
- PPT built from §17's beat list and v1.0's slide outline, updated for the USP.

### 15.2 (b) Before arrival (Plan P only)

Core, W0, W2, console skeleton working end to end on F1; schemas frozen; CI running the 10-minute smoke mission. Nothing architectural is decided on-site.

### 15.3 (c) The on-site build (Plan N shown; Plan P compresses H0–H14)

| Hours | Seat A | Seat B | Seat C | Seat D | Milestone |
|---|---|---|---|---|---|
| 0–2 | Repo, schemas, CI | Schemas, distance-map interface | Vite app, mock `TICK` server | DSL schema, grammar skeleton | Contracts frozen |
| 2–8 | Map, agents, tick loop, damage, survivors | A\*, distance maps, ESA values | C1 map from mock stream | Grammar parser, LLM prompt + cache | — |
| 8–12 | Plume/wind, events, energy | Regret auction, Bayesian search | C1 on live socket, C2 cards | W6 records + templates | **M1: type a mission, agents move** (H12) |
| 12–18 | Radio graph, reserve, leases | Rollout engine + CRN | C4 decision log, event bar | Shield I1–I6 | — |
| 18–20 | Relay placement | Candidates + classifier | C3 fan chart | Escalation manager | **M2: Events 1–4 handled live** (H20) |
| 20–22 | *Buffer 1 — integration defects only* | | | | |
| 22–26 | Evaluation harness, runs | TTI, tuning on F1 seeds 0–49, freeze | C5 escalation dialog + Pareto plot | B1, B2 baselines; hash chain | **M3: full demo script runs** (H26) |
| 26–28 | Held-out runs F1 + F4 | Fix what the runs expose | Projector polish | PPT numbers from registry | — |
| 28–30 | *Buffer 2 — rehearsal and fixes* | | | | |
| 30–32 | Backup video, laptop 2 check | Q&A rehearsal | Freeze UI | Final rehearsal | **Tag demo build; no new features** |

### 15.4 Buffers

Buffer 1 (H20–22) exists because integration always finds schema mismatches and timing bugs; it is not for features. Buffer 2 (H28–30) is for whatever the rehearsals break. If a milestone slips by more than 2 hours, the cut order (§16) is applied immediately rather than renegotiated.

---

## 16. Scope split

| Tier | Items | Reasoning |
|---|---|---|
| **Must** | Core with truth/belief firewall; W0 synthetic F1 + F4; W1 grammar + cached LLM + confirmation; W2 regret auction, A\*, Bayesian search with false alarms, bands; W3 radio graph, computed reserve, leases, relay placement, type-table queue; **W4 rollouts, CRN, candidates (current/repair/veto), fact/value classifier, TTI**; W5 shield + escalation manager; W6 records, templates, hash chain; console C1–C5; evaluation S vs B1, B2; PPT + backup video | Every PS clause, the USP, and the demo's climax |
| **Should** | OSM real map; F2, F3 families; shedding variant; VoI message ranking; replay and fidelity tests; C6 comms queue; C7 after-action report; B3 OR-Tools baseline; USP operator-profile study; 1,000-run suite; held-out parse test | Turn "addressed" into "measured", and make the map real |
| **Could** | CVRPLIB lane; line-of-sight radio; cooperative A\* for multiple rovers; PixiJS renderer; `inspection_crawler` plugin demo | Polish and generality evidence |
| **Won't** | 3D simulation (Gazebo, AirSim, Unity); real hardware; perception, SLAM or obstacle avoidance (excluded by the PS); decentralised consensus planning; adversarial jamming/spoofing models; LLM-generated explanations | Out of scope by the PS, unprovable in the time, or contrary to the fidelity rule |

**Cut order under pressure (first cut first):** (1) Could tier; (2) CVRPLIB and USP operator-profile study → state as designed, not measured; (3) F2, F3 → F1 + F4 only; (4) OSM → synthetic map; (5) B3 → B1 + B2 only; (6) VoI → type-table queue; (7) shedding → escalate when P1 infeasible without offering a shed option; (8) C6, C7 → decision log only. **Never cut:** the truth/belief firewall, Foresight's classifier, the shield, the escalation dialog, the backup video.

**Minimum coherent demo:** synthetic F1 map; five agents; typed mission → DSL; auction and routes; a false-alarm detection verified away and a real one confirmed; comms loss with a lease; an aftershock re-route; one FACT switch and one VALUE escalation with the Pareto dialog; the shield refusing an operator command; S vs B1 on 30 held-out seeds. That touches every clause and the USP.

---

## 17. Demo script — five minutes

Setup: two laptops with identical tagged builds, Wi-Fi off and visibly so; scenario `F1_s0042` (OSM map if built) loaded; Foresight fan chart docked; presenter 1 speaks, presenter 2 drives.

| Beat | Time | What is shown | Intended reaction | Fallback |
|---|---|---|---|---|
| 1 Hook | 0:00–0:20 | Map of a real Mumbai neighbourhood after a simulated quake; five idle agents. "Rescuers will have drones and robots. What they don't have is a way to run them as one team — or to know which decisions a machine should make." | Stakes are clear | Slide |
| 2 Mission | 0:20–0:45 | Type: "Assess the whole area, then search sectors B and C, deliver medkits to anyone found, keep everyone in contact, avoid the smoke." DSL appears as ASR 1 → 2 → 3 phases; operator confirms | "It speaks rescue doctrine" | Cached spec |
| 3 Launch | 0:45–1:15 | Auction bids appear in the log; scouts sweep at high band; relay takes position; heat-map cools as cells are scanned | "It's planning for all of them" | Recorded clip |
| 4 Uncertainty | 1:15–1:50 | Scout-2 reports a heat signature (posterior 0.41) → rover verifies → **false alarm**, closed. A second detection → verified (0.93) → DELIVER P1 spawns, Cargo-1 wins the bid | "It doesn't trust its own sensors blindly" | Narrate from log |
| 5 Comms loss | 1:50–2:25 | Inject: Rover-1 loses link. Card shows lease countdown; its task is held, not duplicated; relay moves; on reconnect its buffered detection jumps the message queue | "It handles silence correctly" | Static panel |
| 6 Aftershock | 2:25–2:55 | Inject aftershock: rubble blocks the rover's road; ghost path shows the old route; Foresight: switch is better on every count → **FACT**, autonomous, explanation shown | "It re-plans alone when the answer is clear" | Screenshot |
| 7 The value question | 2:55–3:50 | Inject wind shift: smoke grows over the survivor. TTI drops to ~5 min. Foresight finds two non-dominated plans; dialog opens: Pareto plot — A: Cargo-1 through the smoke edge, 9 min sooner, 19 % airframe risk; B: rover the long way, 2 % risk. "This is a judgement about acceptable risk, so it is yours." Operator chooses; logged as VALUE with the human's choice | The climax: "it knows what it shouldn't decide" | Pre-rendered dialog |
| 8 Safety | 3:50–4:10 | Presenter tries to force a drone through the plume from the console → **shield refuses**, logged as SAFETY | "Even we can't make it unsafe" | Narrate |
| 9 Judge mode | 4:10–4:35 | Judge picks a seed and injects any event; the swarm responds live | Unscripted credibility | Skip if time is short |
| 10 Evidence | 4:35–5:00 | Registry chart: S vs B1/B2 (and B3 if built) on held-out families with intervals; escalation precision; 0 agent losses in the randomised suite; `verify-log` ✓ | "They measured it, including where it loses" | Printed sheet |

**Honesty line, said once in beat 3:** *"Events are injected so you can see each one; every response is computed live, and the planner never sees where the survivors really are."*

Backup video of a full clean run recorded at H30 on both laptops and a phone; presenter 1 can narrate over it beat for beat.

---

## 18. Novelty and competitive positioning

Product descriptions reflect public material as of October 2026; §7 states what is new, this section states only where each stops. `[VERIFY each against the vendor's current page before the PPT gate]`.

| System | What it does (public description) | Where it stops relative to SAMANVAY |
|---|---|---|
| **Auterion Nemyx** (launched September 2025) | A cross-platform swarm engine on AuterionOS that coordinates drones from different manufacturers as one unit for autonomous multi-target strike missions | Military strike swarms of aerial vehicles. Public material describes coordinated engagement, not heterogeneous air-and-ground search-and-rescue decomposition, belief-based search, or escalation of value trade-offs to an operator (our reading of public material) |
| **FlytBase** | Enterprise platform automating docked-drone operations — one-to-many drones and docks, BVLOS, security, inspection and emergency-response workflows | Aerial docked fleets running configured workflows. No ground robots, no task auction across heterogeneous agents, no forecast-driven re-planning or fact/value escalation (our reading) |
| **QGroundControl / ArduPilot Mission Planner** | Ground-control stations: per-vehicle waypoint missions, telemetry, multi-vehicle display | Mission authoring and monitoring; allocation and re-planning are done by the human `[VERIFY]` |
| **Defence autonomy and C2 platforms** (e.g., Shield AI Hivemind, Anduril Lattice) | Onboard autonomy and multi-asset command and control for military operations `[VERIFY current descriptions]` | Closed military systems; we make no claim about their internals and position SAMANVAY as an open, explainable mission layer for civil disaster response |
| **Research: CBBA, SSI auctions, ConTaCT, adjustable autonomy** | Allocation, communication policies, transfer of control — each studied separately | Each solves one piece; none couples them through one forecast with a fact/value escalation rule (§7.3) |
| **Likely competing teams on EL-05** | A dashboard with nearest-agent assignment and an LLM "planner", or a confidence threshold for escalation `[ASSUMPTION]` | No belief/truth separation, no safety layer independent of the planner, no held-out evidence, and escalation by threshold rather than by the kind of decision |

---

## 19. Operational deployment

### 19.1 Operating model

| Role | Who (assumed) | What they do | Training `[ESTIMATE]` |
|---|---|---|---|
| Mission Commander | USAR team leader (e.g., an NDRF/SDRF team commander) `[ASSUMPTION]` | Sets the objective and signs the policy file (acceptable agent risk, P1 floor, optional exchange rate) | 2 hours on policy and reports |
| Swarm Operator | One per swarm of 5–10 agents `[TARGET, validated by escalations per hour]` | Confirms the mission, monitors, answers escalations, may veto | Half a day on the console + one simulated exercise |
| Field Safety Officer | Launch and recovery crew | Physical safety, batteries, airspace permissions | Existing drone-crew training |
| After-action reviewer | Team or district officer | Reviews the signed log and report after the mission | 1 hour |

Per-mission setup ≈ 10 minutes: load the area map, confirm the policy, type and confirm the mission `[ESTIMATE]`.

### 19.2 Policy and accountability path

1. **Before deployment**, the commander chooses or signs a policy: a preset (cautious / balanced / aggressive) or explicit values. With no exchange rate set, every value trade-off is escalated.
2. **During the mission**, every decision is tagged FACT, VALUE, POLICY or SAFETY. A POLICY decision cites the clause that decided it. A policy change mid-mission is itself a logged, signed decision.
3. **After the mission**, any question — "why was the drone sent into the smoke edge?" — is answered by replaying the signed log: the forecast the system saw, the options it offered, who chose, and when. Accountability rests where the decision was made: the swarm for facts, the human for values.

### 19.3 Deployment cost

| Item | Cost `[ESTIMATE]` |
|---|---|
| Software | ₹0 licence cost: React and FastAPI (MIT), NumPy and SciPy (BSD), OR-Tools (Apache 2.0, evaluation only), osmnx (MIT); OSM data under ODbL with attribution |
| Run-time hardware | One rugged laptop, ≈ ₹1–2 lakh; no GPU required |
| LLM | Optional; a cached or local model removes the recurring cost |
| Drones, robots, radios | Outside SAMANVAY's scope; it sits above whatever fleet the team owns |

### 19.4 Prototype → production

1. **ROS 2 / PX4 adapter** against software-in-the-loop simulation (Gazebo + PX4 SITL) with three simulated airframes — validates that the planner runs unchanged through the adapter.
2. **Hardware-in-the-loop** with two drones and one ground robot in an open field, under applicable drone-rule permissions.
3. **Calibrate Foresight** from flight logs: real drain spreads, detection and false-alarm rates.
4. **Decentralised fallback** (CBBA) so that losing the planner laptop degrades to agent-level coordination rather than to fallback rules alone.
5. **Exercise with a USAR team** — the first time escalations-per-hour and operator response times are measured on real people.

---

## 20. Scalability

### 20.1 Run-time cost `[ESTIMATE — measured at milestone M2 and replaced]`

| Component | Complexity | 5 agents, 30 tasks | 20 agents, 120 tasks | 50 agents, 300 tasks |
|---|---|---|---|---|
| Regret auction (full) | O(T² · A · L) insertion tests | < 50 ms | ≈ 2 s in pure Python | ≈ 30 s — needs restructuring |
| Distance maps | O(T · cells · log cells) on change | < 20 ms | < 80 ms | < 200 ms |
| Foresight batch (N = 64, 120 steps) | O(N · steps · A), vectorised | ≈ 15 ms | ≈ 60 ms | ≈ 150 ms |
| Radio BFS | O(A²) per tick | negligible | negligible | ≈ 1 ms |
| Console render | O(A + cells) per frame | 60 fps | 60 fps | 60 fps with sprite batching |

### 20.2 Load-bearing estimates and the 3× consequence

| Estimate | Decision that rests on it | If 3× worse |
|---|---|---|
| Rollout batch 15 ms | N = 64, 5 candidates, 30 s epochs at 10× speed | Epoch ≈ 450 ms: keep N = 64 at 1–5× speed; at 10× drop to N = 32 (declared in the record) |
| Auction 50 ms | Full re-solve inside each epoch | 150 ms: still fits the 500 ms budget |
| VoI 300 ms | VoI on every congested tick | 900 ms: compute VoI every other epoch; type table in between |
| 24 productive hours per seat | Plan N's Must scope | Cut order applied at the first slipped milestone |

### 20.3 What breaks at scale, and the response

The centralised auction is the first thing to break, at roughly 20 agents in pure Python. Responses in order of cost: vectorise insertion evaluation in NumPy; decompose the area into sectors with one auction per sector and a slow outer loop exchanging tasks between sectors; then move to consensus-based allocation (CBBA) for decentralised operation. Foresight scales linearly and stays cheap. The single base link is the communication bottleneck — the reason message prioritisation exists.

---

## 21. Risk register

P/I = probability/impact (L/M/H). Every mitigation is an action with an owning seat.

| # | Risk | Type | P | I | Mitigation (action, seat) |
|---|---|---|---|---|---|
| R1 | Rules forbid pre-written code | scope | M | H | Plan N ready (§14.3); confirm with organisers this week (D) |
| R2 | Foresight slower than estimated | technical | M | M | Measure at H18; N = 32 and 3 candidates are pre-declared fallbacks (B) |
| R3 | Classifier escalates too often in tuning | technical | M | M | Rate limit and batching already in W5; if F1 tuning shows > 6/hour, raise ε (tolerance) on F1 only and record the value before freezing (B) |
| R4 | Integration slips past H12 | integration | H | H | Mock streams from H2; Buffer 1; cut order (all) |
| R5 | Canvas frame rate drops with overlays | technical | L | M | Layer caching to offscreen canvases; PixiJS swap behind `MapRenderer` (C) |
| R6 | LLM unreachable or slow at venue | demo | M | L | Cache + grammar fallback; demo missions pre-cached (D) |
| R7 | OSM import produces a messy grid | technical | M | L | Largest connected component; synthetic fallback is Must (A) |
| R8 | Judge injects an event that crashes a handler | demo | M | H | 1,000-run randomised suite; every handler wrapped so that an exception holds all agents safely and logs (A, B) |
| R9 | Held-out results show S losing to B3 on ESA | evaluation | M | M | Print it; the pitch rests on escalation quality, safety and explainability, with ESA within a stated margin of an optimiser (D) |
| R10 | Prior art for the USP surfaces | Q&A | L | M | Literature pass before the PPT gate; relabel as Adapted if needed; design unchanged (B, D) |
| R11 | A seat becomes unavailable | team | L | H | Pairing on the critical path; B2 as a working fallback planner (all) |
| R12 | Presentation slot shorter than 5 min | demo | M | M | 3-minute cut: beats 2, 4, 6, 7, 10 (D) |
| R13 | Projector washes out colours | demo | M | L | High-contrast theme toggle tested on a projector (C) |

---

## 22. Judge Q&A — twenty hardest questions

**Q1. How is this different from Auterion's Nemyx or FlytBase?** Nemyx coordinates aerial drones from different manufacturers for strike missions; FlytBase automates docked-drone workflows. Both run fleets of aircraft. SAMANVAY coordinates mixed air and ground agents for search and rescue, re-plans from a forecast of its own uncertainty, and escalates only the decisions that trade one good against another — with every decision explained and signed (§18).

**Q2. Everything you use is published. What did you invent?** The ingredients are published and §7.1 labels each one. What we did not find anywhere is the decision rule: one belief-sampled forecast decides when to re-plan, what to transmit and what to shed, and escalation fires on statistically separated trade-offs rather than low confidence. It is falsifiable — escalation precision ≥ 0.8 against ≤ 0.5 for a threshold rule — and the number is in the registry (§7.3).

**Q3. Why an auction and not an optimal solver or reinforcement learning?** An auction is fast, re-plans locally, and every bid is an explanation. We measure its quality against an OR-Tools optimiser (B3) rather than assume it. Reinforcement learning would need training we cannot validate and would make decisions we could not explain.

**Q4. Is this real, or an animation?** The world is simulated; every decision is computed live. Pick a seed and inject any event (judge mode).

**Q5. Does the planner know where the survivors are?** No. Ground truth and belief are separate types; planning code cannot import the truth, and CI fails if it does. Detections are uncertain both ways — you saw a false alarm verified away.

**Q6. What if the LLM misreads the mission?** It only proposes a specification, which is schema-validated and shown to the operator before launch. It never allocates, routes or explains. Measured parse accuracy on 40 held-out objectives is in the registry; a grammar fallback works with the LLM offline.

**Q7. Where do your numbers come from?** Every threshold is either a procedure (reserves from distance-to-charger and drain spread; switching from paired confidence intervals) or a labelled operator policy (triage weights, acceptable risk). Scenario parameters are ours and stated as such.

**Q8. Why not just escalate when confidence is low?** Because low confidence does not mean a human can do better. If one option is clearly least bad, asking only adds delay. Humans add value when the choice depends on what we are willing to trade, or when the committed mission is failing — those are exactly our two triggers.

**Q9. Won't the operator be flooded?** Escalations are rate-limited, batched and carry a default with a deadline. Escalations per mission-hour is a measured metric with a target of ≤ 6. A commander can also pre-set the exchange rate, after which value decisions run under policy and are logged as such.

**Q10. What happens when an agent loses comms — won't you duplicate work?** Its tasks are held under a lease sized to its own predicted completion time, then released if it stays silent. On reconnect, completions are reconciled and duplicates counted; that count is lower than for the baselines.

**Q11. What if your forecast model is wrong?** Then forecasts are overconfident. Foresight's model is deliberately simpler than the simulator, and we run it with wrong parameters on purpose (§13.2). The expected effect is more shield interventions and escalations, not agent losses.

**Q12. What stops a drone flying into the smoke if your planner is wrong?** An independent shield with no planner code in it checks every route against hard limits and overrides it. You saw it refuse our own command.

**Q13. Would this work on real robots?** The planner talks to agents through a three-method adapter. A ROS 2 or MAVLink implementation of those methods is the integration path; the first production step is PX4 software-in-the-loop (§19.4).

**Q14. What if the laptop running the planner dies?** Agents fall back to onboard rules: finish the queue, return at reserve, return if silent too long. Decentralised allocation (CBBA) is the production answer and is stated as not built.

**Q15. Does it scale to 50 agents?** Not as built. The centralised auction is fine to about 20 agents; beyond that the design is sector-decomposed auctions and then CBBA. Foresight scales linearly (§20).

**Q16. What about jamming, GPS spoofing or a hacked drone?** Out of scope and stated. Command signing belongs in the adapter (MAVLink 2 signing, ROS 2 security) and does not change the planner.

**Q17. How do you know it works?** Tuned on one scenario family, frozen, tested on three families it never saw, against four baselines including an optimiser, paired by seed with confidence intervals — and every row printed, including the ones where we lose.

**Q18. Why simulation and not hardware?** The PS asks for mission-level autonomy, not flight control, and simulation is the only way to test hundreds of disruption scenarios with known truth. The adapter is how it meets hardware.

**Q19. Why 2D?** Mission-level decisions — who, what, when, which route — do not need 3D rendering. Altitude is modelled as separation bands. Time went into the planner instead.

**Q20. Who would use this, and what does it cost?** A USAR team's drone cell: a commander sets policy, one operator supervises five to ten agents. The software is open-source components on one laptop; the fleet is whatever the team already owns (§19).

---

## 23. Self-assessment

Scored against eight dimensions a technical jury typically uses. The v1.0 column is our own estimate of the blueprint; neither column is an external review.

| Dimension | v1.0 | v2.0 | Justification and what still falls short |
|---|---|---|---|
| PS requirement coverage | 8.0 | **9.0** | Every clause has a mechanism, including "terminate part of the mission" and "which observations to transmit". Not higher because VoI ranking and shedding are Should-tier and may ship as type-table priorities and escalate-only. |
| Technical soundness | 6.5 | **8.5** | Single currency, regret auction, two-sided detection uncertainty, leases, computed reserves, an independent shield, a truth/belief firewall. **Short of 9** because Foresight's stochastic model is hand-specified; its calibration is only tested by the misspecification experiment, not against real data. |
| Novelty & innovation | 6.0 | **8.0** | One Invented row with a stated falsification and literature gap. **Short of 9** because each ingredient is published; a reviewer who insists on a new algorithm will call the fact/value rule Adapted, and we would rather state that than inflate it. |
| Technical feasibility | 7.5 | **7.0** | v2.0 is more ambitious. The ledger closes only with pre-building (Plan P) or a reduced Must (Plan N). This is the weakest dimension. |
| Demo & visual quality | 7.5 | **8.5** | A real-street map, live re-plan ghosts, a fan chart, a Pareto dialog as the climax, a live false alarm, a shield refusal, judge mode. 2D only. |
| Impact & operational relevance | 7.0 | **8.5** | INSARAG-aligned phases, an operating model with roles and policy, accountability by signed replay, cost, a production path. **Short of 9** because no responder has validated the workflow. |
| Scalability | 7.0 | **7.5** | Honest limits and a staged response; the centralised auction remains the ceiling. |
| Evaluation design | 5.5 | **9.0** | Held-out families, frozen commit, optimiser baseline, paired statistics, pre-registered USP targets, randomised safety suite. **Short of 9.5** because every scenario is ours; the CVRPLIB lane checks only the heuristic, not the mission. |

**The remaining weak point, named:** feasibility. If the organisers forbid pre-written code, Plan N keeps the USP and the safety layer but thins the evidence to two families and three baselines. The architecture is designed so that each cut leaves a coherent, honestly labelled system rather than a broken one.

---

## 24. Change register — v1.0 blueprint → v2.0

The body states one design. This table records every decision that changed, so the specification never contains two answers to the same question.

| # | What changed | From (v1.0) | To (v2.0) | Why | Where |
|---|---|---|---|---|---|
| C-01 | Name | SwarmCommand | SAMANVAY (either acceptable) | Identity for the pitch | Header |
| C-02 | Bid cost | Weighted sum of four unlike terms | ESA currency; energy and comms as constraints; agent risk as a separate outcome | Weights were unjustifiable | §6.3.2 |
| C-03 | Auction | Append to end, cheapest pair first | Cheapest insertion, regret selection | Known quality improvement | §6.3.3 |
| C-04 | Detection | Misses only | Misses and false alarms, Bayesian map | Verification must be meaningful | §6.3.4 |
| C-05 | Comms loss | Agent continues; tasks may be reassigned | Leases with predicted-completion expiry; reconciliation | Duplicate work | §6.4.3 |
| C-06 | Confidence and escalation | Min of four undefined scores < 0.5 | Foresight rollouts; fact/value classification | Undefined numbers; wrong trigger | §6.5 |
| C-07 | Battery reserve | Flat 20 % | Distance-to-charger × (1 + 2 cv) | Context-dependent | §6.4.2 |
| C-08 | Re-plan switching | Fixed 15 % hysteresis | Paired forecast difference with 95 % interval | Arbitrary constant | §6.5.4 |
| C-09 | Safety | Planner trusted | Independent shield, invariants I1–I6 | Planner errors were unbounded | §6.6 |
| C-10 | Weather | One sentence | Wind field + advecting plume; planning against forecast | No mechanism | §6.1.4 |
| C-11 | Deconfliction | None | Altitude bands + shield I4 | Collisions | §6.3.5 |
| C-12 | Task shedding | Absent | Shedding candidates; P1 shedding always escalated | PS clause unmet | §6.5.3 |
| C-13 | LLM role | Decomposition + optional rephrasing | Decomposition only, into an INSARAG-phased DSL | Explanation fidelity; doctrine | §6.2, §6.7 |
| C-14 | Evaluation | One naive baseline on our scenario | Four baselines incl. OR-Tools; held-out families; frozen commit | Self-grading | §10 |
| C-15 | Map | Synthetic | OSM real neighbourhood (Should), synthetic fallback | Impact | §6.1.1 |
| C-16 | Truth/belief | Implicit | Separate types, CI-enforced firewall | One import would invalidate results | §5.4 |
| C-17 | Effort plan | 32 h assumed sufficient | Person-hour ledger, Plan P / Plan N | Did not close | §14.3 |

**Decisions deliberately unchanged:** the Python backend with a React console (RD-1, RD-2); a centralised planner (RD-7); 2D (RD-5); the disaster-response framing of EL-05 in the demo.

---

## References

- Alshiekh, M., et al. (2018). Safe reinforcement learning via shielding. *AAAI*.
- Bourgault, F., Furukawa, T., & Durrant-Whyte, H. F. (2003). Optimal search for a lost target in a Bayesian world. *Field and Service Robotics*.
- Choi, H.-L., Brunet, L., & How, J. P. (2009). Consensus-based decentralized auctions for robust task allocation. *IEEE Transactions on Robotics*.
- Gerkey, B. P., & Matarić, M. J. (2004). A formal analysis and taxonomy of task allocation in multi-robot systems. *International Journal of Robotics Research*.
- Gray, C., & Cheriton, D. (1989). Leases: an efficient fault-tolerant mechanism for distributed file cache consistency. *SOSP*.
- Hart, P. E., Nilsson, N. J., & Raphael, B. (1968). A formal basis for the heuristic determination of minimum cost paths. *IEEE Transactions on Systems Science and Cybernetics*.
- INSARAG (UN OCHA). *INSARAG Guidelines, Vol. III, Annex B20: Assessment, Search and Rescue Levels.*
- Koenig, S., et al. (2006). The power of sequential single-item auctions for agent coordination. *AAAI*.
- Krarup, B., et al. (2021). Contrastive explanations of plans through model restrictions. *Journal of Artificial Intelligence Research*.
- Lagoudakis, M. G., et al. (2005). Auction-based multi-robot routing. *Robotics: Science and Systems*.
- Parasuraman, R., Sheridan, T. B., & Wickens, C. D. (2000). A model for types and levels of human interaction with automation. *IEEE Transactions on Systems, Man, and Cybernetics — Part A*.
- Roijers, D. M., Vamplew, P., Whiteson, S., & Dazeley, R. (2013). A survey of multi-objective sequential decision-making. *Journal of Artificial Intelligence Research*.
- Scerri, P., Pynadath, D. V., & Tambe, M. (2002). Towards adjustable autonomy for the real world. *Journal of Artificial Intelligence Research*.
- Sha, L. (2001). Using simplicity to control complexity. *IEEE Software*.
- Silver, D. (2005). Cooperative pathfinding. *AIIDE*.
- Stone, L. D. (1975). *Theory of Optimal Search.* Academic Press.
- Unhelkar, V. V., & Shah, J. A. (2016). ConTaCT: Deciding to communicate during time-critical collaborative tasks in unknown, deterministic domains. *AAAI*.

`[VERIFY: author lists and venues for every reference before they appear on a slide; those marked "et al." in particular.]`
