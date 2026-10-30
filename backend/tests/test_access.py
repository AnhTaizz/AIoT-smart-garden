"""Pump commands stay local until the API has authentication (BC-02)."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.access import is_remote
from app.config import Settings
from app.main import app


@pytest.mark.parametrize("headers, client_host", [
    ({}, "127.0.0.1"),
    ({}, "172.18.0.1"),  # Docker bridge gateway in front of the API port
    ({"x-real-ip": "172.18.0.5", "x-forwarded-for": "192.168.1.23"}, "172.18.0.5"),  # LAN phone via Nginx
    ({"x-forwarded-for": "10.0.0.2, 172.18.0.1"}, "172.18.0.5"),
    ({"forwarded": 'for="[fd00::7]:5000";proto=http'}, "::1"),
    ({"x-forwarded-for": "100.64.3.4"}, "127.0.0.1"),  # CGNAT/VPN range is not public
    ({}, "testclient"),
    ({}, None),
])
def test_laptop_docker_and_lan_requests_are_local(headers, client_host):
    assert is_remote(headers, client_host) is False


@pytest.mark.parametrize("headers, client_host", [
    ({"cf-connecting-ip": "203.0.113.9"}, "127.0.0.1"),  # Cloudflare Quick Tunnel
    ({"cf-ray": "8f00000000000000-SIN"}, "172.18.0.1"),
    ({"cdn-loop": "cloudflare; loops=1"}, "127.0.0.1"),
    ({"x-forwarded-for": "1.1.1.1"}, "127.0.0.1"),  # ngrok-style tunnel
    ({"x-forwarded-for": "192.168.1.5, 1.1.1.1"}, "127.0.0.1"),
    ({"forwarded": "for=1.1.1.1"}, "127.0.0.1"),
    ({"x-forwarded-for": "::ffff:1.1.1.1"}, "127.0.0.1"),
    ({"x-forwarded-for": "unknown"}, "127.0.0.1"),  # unparsable hop fails closed
    ({}, "8.8.8.8"),  # API port reached directly from the Internet
])
def test_tunnel_and_public_requests_are_remote(headers, client_host):
    assert is_remote(headers, client_host) is True


@pytest.fixture
def api(monkeypatch):
    bridge = MagicMock()
    bridge.is_connected.return_value = False
    monkeypatch.setattr(app.state, "settings", Settings.from_env(), raising=False)
    monkeypatch.setattr(app.state, "bridge", bridge, raising=False)
    monkeypatch.setattr(app.state, "pool", MagicMock(), raising=False)
    client = TestClient(app)  # Deliberately no lifespan: DB/MQTT stay isolated.
    yield client, bridge
    client.close()


def test_remote_pump_on_is_refused_before_db_or_mqtt(api):
    client, bridge = api
    response = client.post(
        "/devices/node_01/commands",
        json={"action": "pump_on", "duration_seconds": 5},
        headers={"cf-connecting-ip": "203.0.113.9", "cf-ray": "abc-SIN"},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "remote_control_disabled"
    assert "xác thực" in response.json()["detail"]["message"]
    bridge.is_connected.assert_not_called()
    bridge.publish.assert_not_called()
    app.state.pool.connection.assert_not_called()


def test_remote_pump_off_is_also_refused(api):
    client, bridge = api
    response = client.post(
        "/devices/node_01/commands", json={"action": "pump_off"},
        headers={"x-forwarded-for": "1.1.1.1"},
    )
    assert response.status_code == 403
    bridge.publish.assert_not_called()


def test_local_command_passes_the_guard(api):
    client, bridge = api
    response = client.post(
        "/devices/node_01/commands", json={"action": "pump_off"},
        headers={"x-forwarded-for": "192.168.1.23"},
    )
    # Reaches the normal command path, which then reports the broker state.
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "mqtt_unavailable"
    bridge.is_connected.assert_called_once()


def test_control_access_endpoint_reports_capability(api):
    client, _ = api
    assert client.get("/control-access").json() == {"commands_allowed": True, "reason": None}
    remote = client.get("/control-access", headers={"cf-ray": "abc-SIN"})
    assert remote.status_code == 200
    assert remote.json() == {"commands_allowed": False, "reason": "remote_control_disabled"}


def test_remote_clients_can_still_read(api):
    client, _ = api
    assert client.get("/health", headers={"cf-ray": "abc-SIN"}).json() == {"status": "ok"}
