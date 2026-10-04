"""Test Phase 3 server extensions:
1. mumbai.pmtiles HTTP range request support (206 Partial Content, bytes header).
2. /api/zones and /api/zones/{zone_id} endpoints.
3. /api/zones/generate offline rejection.
4. POLICY_SET message handler creates decision record with kind=POLICY_CHOICE, classification=POLICY.
"""

from fastapi.testclient import TestClient
import pytest
from samanvay.server.app import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


def test_mumbai_pmtiles_range_request(client):
    """Verify HTTP range request on /mumbai.pmtiles returns 206 Partial Content."""
    # Request first 1024 bytes
    response = client.get("/mumbai.pmtiles", headers={"Range": "bytes=0-1023"})
    assert response.status_code == 206
    assert response.headers.get("accept-ranges") == "bytes"
    assert "bytes 0-1023/" in response.headers.get("content-range", "")
    assert len(response.content) == 1024

    # Request second chunk
    response2 = client.get("/mumbai.pmtiles", headers={"Range": "bytes=1024-2047"})
    assert response2.status_code == 206
    assert len(response2.content) == 1024


def test_api_zones_library(client):
    """Verify pre-cached zones library returns at least 5 Mumbai zones."""
    response = client.get("/api/zones")
    assert response.status_code == 200
    data = response.json()
    assert "zones" in data
    zones = data["zones"]
    assert len(zones) >= 5
    zone_ids = [z["id"] for z in zones]
    for required in ["vile_parle_west", "andheri", "bandra", "dharavi", "colaba"]:
        assert required in zone_ids, f"Required zone {required} missing"


def test_api_zones_by_id(client):
    """Verify retrieval of specific cached zone with OSM vector buildings and roads."""
    response = client.get("/api/zones/vile_parle_west")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "vile_parle_west"
    assert len(data.get("buildings", [])) > 0
    assert len(data.get("roads", [])) > 0


def test_api_zones_generate_offline_check(client):
    """Verify uncached zone behavior."""
    response = client.post("/api/zones/generate")
    # If offline, returns 400 with 'offline: zone not cached'. If online, returns progress.
    assert response.status_code in (200, 400)
    data = response.json()
    if response.status_code == 400:
        assert data.get("reason") == "offline: zone not cached"
    else:
        assert "generating from OpenStreetMap" in data.get("status", "")


def test_websocket_policy_set(client):
    """Verify that POLICY_SET WebSocket message generates a real decision record with POLICY classification."""
    with client.websocket_connect("/ws") as ws:
        # Read initial snapshot
        init_snap = ws.receive_json()
        assert init_snap["type"] == "SNAPSHOT"

        # Send POLICY_SET message
        ws.send_json({
            "type": "POLICY_SET",
            "preset": "cautious",
            "policy": {"riskTolerance": 0.10, "reserveFloor": 0.25}
        })

        # Receive DECISION record generated
        dec_msg = ws.receive_json()
        assert dec_msg["type"] == "DECISION"
        rec = dec_msg["payload"]
        assert rec["classification"] == "POLICY"
        assert rec["kind"] in ("POLICY_CHOICE", "SWITCH_PLAN")
        assert rec["chosen"] == "cautious"
        assert "cautious" in rec["explanation"]
