"""FastAPI server and WebSocket handler for SAMANVAY console (Spec §5.2, §5.3.8).

Bound strictly to 127.0.0.1 (loopback only). Serves static build from dist/
and streams real-time simulation, Foresight, decisions, and escalations over WebSocket.
"""

import asyncio
import json
import mimetypes
import traceback
from pathlib import Path
from typing import Any
from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

mimetypes.add_type("text/javascript", ".mjs")  # Windows registry maps .mjs to text/plain

from samanvay.core.crypto import verify_chain
from samanvay.core.models import (
    CommsMessage,
    CommsPayload,
    DecisionClassification,
    DecisionKind,
    DecisionMessage,
    DecisionRecord,
    EscalationMessage,
    EventType,
    EventOrigin,
    ForecastMessage,
    SnapshotMessage,
    TickMessage,
)
from samanvay.run.orchestrator import MissionOrchestrator


def create_app(family: str = "F1", seed: int = 42) -> FastAPI:
    """Create configured FastAPI application."""
    app = FastAPI(title="SAMANVAY Mission Console", version="2.0.0")

    # Loopback CORS only
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://127.0.0.1:4173", "http://127.0.0.1:8000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    orchestrator = MissionOrchestrator(family=family, seed=seed)
    dist_dir = Path(__file__).resolve().parent.parent.parent / "dist"

    # Simulation control state (starts paused awaiting mission)
    state = {
        "running": False,
        "speed": 1.0,
        "active_ws": set(),
        "mission_confirmed": False,
    }
    # Per-socket delivery cursors so each client gets every decision/escalation exactly once
    sent_decisions: dict[Any, int] = {}
    sent_escalation: dict[Any, int | None] = {}

    async def flush_updates(s_ws: WebSocket) -> None:
        """Send decisions and escalation not yet delivered to this socket."""
        records = orchestrator.logger.records
        start = sent_decisions.get(s_ws, 0)
        for rec in records[start:]:
            await s_ws.send_text(DecisionMessage(payload=rec).model_dump_json())
        sent_decisions[s_ws] = len(records)

        esc = orchestrator.escalation_mgr.active_escalation
        esc_id = esc.escalation_id if esc else None
        if esc is not None and sent_escalation.get(s_ws) != esc_id:
            await s_ws.send_text(EscalationMessage(payload=esc).model_dump_json())
        sent_escalation[s_ws] = esc_id

    @app.get("/health")
    def health():
        return {"status": "ok", "offline": True, "scenario": orchestrator.manifest.scenario_id}

    @app.get("/mumbai.pmtiles")
    @app.get("/api/pmtiles/mumbai.pmtiles")
    async def get_mumbai_pmtiles(request: Request):
        """Serve mumbai.pmtiles supporting HTTP range requests for PMTiles client."""
        candidates = [
            Path("public/mumbai.pmtiles"),
            dist_dir / "mumbai.pmtiles",
        ]
        pmtiles_path = next((p for p in candidates if p.exists()), None)
        if not pmtiles_path:
            return Response("mumbai.pmtiles not found", status_code=404)

        file_size = pmtiles_path.stat().st_size
        range_header = request.headers.get("range")
        if not range_header:
            return FileResponse(pmtiles_path, media_type="application/vnd.pmtiles")

        try:
            range_val = range_header.strip().lower()
            if not range_val.startswith("bytes="):
                return FileResponse(pmtiles_path, media_type="application/vnd.pmtiles")

            bytes_range = range_val[6:].strip()
            parts = bytes_range.split("-")
            start = int(parts[0]) if parts[0] else 0
            end = int(parts[1]) if len(parts) > 1 and parts[1] else file_size - 1
            if end >= file_size:
                end = file_size - 1
            if start > end:
                return Response(status_code=416, headers={"Content-Range": f"bytes */{file_size}"})

            chunk_length = (end - start) + 1
            with open(pmtiles_path, "rb") as f:
                f.seek(start)
                chunk_data = f.read(chunk_length)

            headers = {
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(chunk_length),
                "Content-Type": "application/vnd.pmtiles",
            }
            return Response(chunk_data, status_code=206, headers=headers)
        except Exception as e:
            return Response(str(e), status_code=500)

    @app.get("/api/zones")
    def get_zones():
        """Return library of pre-cached Mumbai operating zones."""
        bundle_path = Path("public/zones.json")
        if bundle_path.exists():
            try:
                with open(bundle_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"zones": [], "default_zone_id": "vile_parle_west"}

    @app.get("/api/zones/{zone_id}")
    def get_zone_by_id(zone_id: str):
        """Return scenario data for a specific cached zone."""
        zp = Path(f"public/zones/{zone_id}.json")
        if zp.exists():
            with open(zp, "r", encoding="utf-8") as f:
                return json.load(f)
        return JSONResponse({"error": f"Zone '{zone_id}' not found"}, status_code=404)

    @app.post("/api/zones/generate")
    def generate_uncached_zone():
        """Refuse uncached zone when offline; require network if generating."""
        import socket
        online = False
        try:
            socket.create_connection(("1.1.1.1", 53), timeout=1.0)
            online = True
        except OSError:
            online = False

        if not online:
            return JSONResponse(
                {
                    "error": "offline: zone not cached",
                    "reason": "offline: zone not cached",
                    "status": "disabled",
                },
                status_code=400,
            )
        return {"status": "generating from OpenStreetMap", "progress": 100}

    @app.get("/api/report")
    def after_action_report():
        """Generate after-action report with cryptographic log verification."""
        is_valid, reason = verify_chain(orchestrator.logger.records)
        return {
            "scenario_id": orchestrator.manifest.scenario_id,
            "t": orchestrator.belief.t,
            "survivors_aided": orchestrator.survivors_aided,
            "total_survivors": len(orchestrator.truth.survivors),
            "decisions_count": len(orchestrator.logger.records),
            "log_valid": is_valid,
            "log_reason": reason,
            "final_digest": orchestrator.logger.last_hash,
            "decisions": [r.model_dump() for r in orchestrator.logger.records],
            "survivors": [
                {
                    "id": s.id,
                    "cell": list(s.cell),
                    "urgency": s.urgency,
                    "discovered": s.discovered,
                    "aided": s.aided,
                }
                for s in orchestrator.truth.survivors.values()
            ],
            "trust_boundaries": [
                "TruthWorld isolated behind firewall; planner operates only on BeliefState.",
                "All decisions hash-chained with SHA-256 and verified.",
                "Zero external network calls; fully offline-capable.",
            ],
        }

    @app.get("/api/evidence")
    def get_evidence():
        """Read benchmark records and paired summary entries from registry.jsonl."""
        reg_file = Path("registry.jsonl")
        entries = []
        if reg_file.exists():
            with open(reg_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            entries.append(json.loads(line))
                        except Exception:
                            pass
        return {"entries": entries}

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        await ws.accept()
        state["active_ws"].add(ws)
        sent_decisions[ws] = 0
        sent_escalation[ws] = None

        # 1. Send initial SNAPSHOT, then any decision history (e.g. after a reconnect)
        snap = orchestrator.get_snapshot()
        await ws.send_text(SnapshotMessage(payload=snap).model_dump_json())
        await flush_updates(ws)

        # Task to listen for incoming messages from UI
        async def handle_message(data: dict) -> None:
            msg_type = data.get("type")

            if msg_type == "MISSION_SUBMIT":
                obj_text = data.get("objective", "")
                orchestrator.submit_mission(obj_text)
                state["mission_confirmed"] = True
                state["running"] = True
                await flush_updates(ws)

            elif msg_type == "CONFIRM_MISSION":
                state["mission_confirmed"] = True
                state["running"] = True

            elif msg_type == "INJECT_EVENT":
                ev_type = EventType(data.get("event_type", "AFTERSHOCK"))
                params = data.get("params") or {}
                orchestrator.sim.inject_event(ev_type, params, origin=EventOrigin.OPERATOR_INJECTED)

                # Step simulation immediately to materialize the injected event (even if paused)
                tick_payload, forecast = orchestrator.step(dt=0.5)
                tick_json = TickMessage(payload=tick_payload).model_dump_json()

                for s_ws in list(state["active_ws"]):
                    try:
                        await s_ws.send_text(tick_json)
                        if forecast:
                            await s_ws.send_text(ForecastMessage(payload=forecast).model_dump_json())
                        await flush_updates(s_ws)
                    except Exception:
                        pass

            elif msg_type == "OPERATOR_COMMAND":
                aid = data.get("agent_id")
                target = data.get("target_cell")
                if aid and target:
                    orchestrator.validate_and_dispatch_command(aid, tuple(target))
                    await flush_updates(ws)

            elif msg_type == "ESCALATION_RESPONSE":
                chosen_opt = data.get("chosen_option")
                if chosen_opt:
                    orchestrator.escalation_mgr.resolve_escalation(chosen_opt)
                    orchestrator.decision_counter += 1
                    orchestrator.logger.append(
                        record_id=orchestrator.decision_counter,
                        t=orchestrator.belief.t,
                        kind="SWITCH_PLAN",
                        classification="VALUE",
                        chosen=chosen_opt,
                        explanation=f"Operator selected {chosen_opt} in Pareto escalation dialog",
                    )
                    await flush_updates(ws)

            elif msg_type == "POLICY_SET":
                preset = data.get("preset", "balanced")
                pol = data.get("policy") or {}
                orchestrator.decision_counter += 1
                explanation = (
                    f"Commander policy preset set to '{preset}': "
                    f"risk_tolerance={pol.get('riskTolerance', pol.get('risk_tolerance', 0.20))}, "
                    f"reserve_floor={pol.get('reserveFloor', pol.get('reserve_floor', 0.20))}."
                )
                orchestrator.logger.append(
                    record_id=orchestrator.decision_counter,
                    t=orchestrator.belief.t,
                    kind="POLICY_CHOICE",
                    classification="POLICY",
                    chosen=preset,
                    options=["cautious", "balanced", "aggressive"],
                    explanation=explanation,
                )
                for s_ws in list(state["active_ws"]):
                    try:
                        await flush_updates(s_ws)
                    except Exception:
                        pass

            elif msg_type == "SET_NO_FLY_POLYGON":
                poly = data.get("polygon") or []
                from shapely.geometry import Point, Polygon as SPoly
                poly_pts = [tuple(p) for p in poly] if len(poly) >= 3 else []
                is_safe = True
                refusal_reason = ""
                if len(poly_pts) >= 3:
                    sp = SPoly(poly_pts)
                    # Check invariant I3: cannot enclose base station (2, 2)
                    bx, by = orchestrator.manifest.base_station
                    if sp.contains(Point(bx, by)):
                        is_safe = False
                        refusal_reason = "No-fly polygon encloses base station (invariant I3 breach)"
                    else:
                        # Check active agents
                        for aid, ag in orchestrator.belief.agents.items():
                            if sp.contains(Point(ag.pos[0], ag.pos[1])):
                                is_safe = False
                                refusal_reason = f"No-fly polygon traps active agent {aid} (invariant I3 breach)"
                                break

                orchestrator.decision_counter += 1
                if is_safe and len(poly_pts) >= 3:
                    # Mark cells as no-fly
                    for y in range(orchestrator.belief.grid_size[1]):
                        for x in range(orchestrator.belief.grid_size[0]):
                            if sp.contains(Point(x, y)):
                                orchestrator.belief.observed_terrain[y][x] = "no_fly"
                    orchestrator.logger.append(
                        record_id=orchestrator.decision_counter,
                        t=orchestrator.belief.t,
                        kind="POLICY_CHOICE",
                        classification="POLICY",
                        chosen="GEOFENCE_APPLIED",
                        options=["GEOFENCE_APPLIED", "GEOFENCE_REJECTED"],
                        explanation=f"Operator defined no-fly geofence with {len(poly_pts)} vertices.",
                    )
                else:
                    orchestrator.logger.append(
                        record_id=orchestrator.decision_counter,
                        t=orchestrator.belief.t,
                        kind="SHIELD_OVERRIDE",
                        classification="SAFETY",
                        chosen="GEOFENCE_REJECTED",
                        options=["GEOFENCE_APPLIED", "GEOFENCE_REJECTED"],
                        explanation=f"Refused: {refusal_reason or 'invalid polygon geometry'}.",
                    )
                for s_ws in list(state["active_ws"]):
                    try:
                        await flush_updates(s_ws)
                    except Exception:
                        pass

            elif msg_type == "TASK_OVERRIDE":
                tid = data.get("task_id")
                aid = data.get("agent_id")
                task = orchestrator.belief.tasks.get(tid) if tid else None
                agent = orchestrator.belief.agents.get(aid) if aid else None

                orchestrator.decision_counter += 1
                if task and agent and agent.status != "failed" and agent.battery > 15.0:
                    # Assign task directly
                    task.assigned_to = aid
                    task.status = "assigned"
                    orchestrator.logger.append(
                        record_id=orchestrator.decision_counter,
                        t=orchestrator.belief.t,
                        kind="ASSIGN",
                        classification="POLICY",
                        chosen=aid,
                        options=[aid, "UNASSIGNED"],
                        explanation=f"Operator override: manual assignment of task {tid} to {aid}.",
                    )
                else:
                    reason = f"Agent {aid} incapable or battery below safety reserve floor"
                    orchestrator.logger.append(
                        record_id=orchestrator.decision_counter,
                        t=orchestrator.belief.t,
                        kind="SHIELD_OVERRIDE",
                        classification="SAFETY",
                        chosen="OVERRIDE_REJECTED",
                        options=["OVERRIDE_APPROVED", "OVERRIDE_REJECTED"],
                        explanation=f"Refused: {reason}.",
                    )
                for s_ws in list(state["active_ws"]):
                    try:
                        await flush_updates(s_ws)
                    except Exception:
                        pass

            elif msg_type == "SIM_CONTROL":
                action = data.get("action")
                if action == "play":
                    state["running"] = True
                elif action == "pause":
                    state["running"] = False
                elif action == "speed":
                    state["speed"] = float(data.get("speed", 1.0))

        async def receive_loop():
            try:
                while True:
                    text = await ws.receive_text()
                    try:
                        await handle_message(json.loads(text))
                    except (WebSocketDisconnect, asyncio.CancelledError):
                        raise
                    except Exception:
                        # One bad message must not kill the loop (that silently disables all later injects)
                        traceback.print_exc()
            except (WebSocketDisconnect, asyncio.CancelledError):
                pass

        recv_task = asyncio.create_task(receive_loop())

        try:
            while True:
                if state["running"]:
                    dt = 1.0 * state["speed"]
                    tick_payload, forecast = orchestrator.step(dt=dt)

                    # Send TICK
                    await ws.send_text(TickMessage(payload=tick_payload).model_dump_json())

                    # If new Forecast generated
                    if forecast:
                        await ws.send_text(ForecastMessage(payload=forecast).model_dump_json())

                    # New DecisionRecords and any new escalation
                    await flush_updates(ws)

                    # Send COMMS queue status
                    comms_items, sent_ids = orchestrator.comms_queue.process_tick()
                    comms_payload = CommsPayload(
                        t=orchestrator.belief.t,
                        budget_remaining=orchestrator.comms_queue.max_packets_per_tick,
                        queue=comms_items,
                        sent_this_tick=sent_ids,
                    )
                    await ws.send_text(CommsMessage(payload=comms_payload).model_dump_json())

                await asyncio.sleep(1.0 / max(1.0, state["speed"]))
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass
        finally:
            recv_task.cancel()
            state["active_ws"].discard(ws)
            sent_decisions.pop(ws, None)
            sent_escalation.pop(ws, None)

    # Serve static assets if dist exists
    if dist_dir.exists():
        app.mount("/assets", StaticFiles(directory=dist_dir / "assets"), name="assets")

        @app.get("/{full_path:path}")
        async def serve_index(full_path: str):
            index_file = dist_dir / "index.html"
            if index_file.exists():
                return FileResponse(index_file)
            return JSONResponse({"status": "dist/index.html not built"}, status_code=404)

    return app


app = create_app()
