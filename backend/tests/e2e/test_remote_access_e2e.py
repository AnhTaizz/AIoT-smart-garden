"""BC-01: remote clients read data but cannot publish pump commands.

Runs against the real backend, PostgreSQL and Mosquitto. The Nginx cases also
need E2E_PROXY_URL (the dashboard `/api` proxy) to prove forwarded headers
survive the Web path used by tunnels.
"""

import json
import os
import queue
import urllib.error
import urllib.request

import pytest

from helpers import API, FakeDevice, request

pytestmark = pytest.mark.skipif(not API, reason="E2E_API_BASE_URL not set")
PROXY = os.getenv("E2E_PROXY_URL", "").rstrip("/")
# What Cloudflare adds to every request that crossed a Quick Tunnel.
CLOUDFLARE = {"Cf-Connecting-Ip": "1.1.1.1", "Cf-Ray": "8f00e2e000000000-SIN"}


def call(base, method, path, body=None, headers=None):
    req = urllib.request.Request(
        base + path,
        data=None if body is None else json.dumps(body).encode(),
        method=method,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status, json.loads(response.read() or b"null")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"null")


def assert_nothing_published(device):
    with pytest.raises(queue.Empty):
        device.control.get(timeout=1.5)
    assert request("GET", f"/devices/{device.device_id}/commands")[1]["count"] == 0


@pytest.mark.parametrize("headers", [
    CLOUDFLARE,
    {"X-Forwarded-For": "1.1.1.1"},
])
def test_remote_pump_on_is_refused_and_never_stored_or_published(headers):
    with FakeDevice() as device:
        device.announce()
        status, body = call(
            API, "POST", f"/devices/{device.device_id}/commands",
            {"action": "pump_on", "duration_seconds": 5}, headers,
        )
        assert status == 403, body
        assert body["detail"]["code"] == "remote_control_disabled"
        assert_nothing_published(device)
        assert device.state()["relay_state"] == "off"


def test_remote_client_still_reads_state_and_telemetry():
    with FakeDevice() as device:
        device.announce()
        device.publish_telemetry()
        device.wait_for_count(1)
        assert call(API, "GET", "/control-access", headers=CLOUDFLARE)[1] == {
            "commands_allowed": False, "reason": "remote_control_disabled",
        }
        status, latest = call(API, "GET", f"/devices/{device.device_id}/latest", headers=CLOUDFLARE)
        assert status == 200 and latest["simulated"] is True
        status, state = call(API, "GET", f"/devices/{device.device_id}/state", headers=CLOUDFLARE)
        assert status == 200 and state["relay_state"] == "off"


def test_local_command_still_completes_full_lifecycle():
    with FakeDevice(auto_respond=True) as device:
        device.announce()
        assert request("GET", "/control-access") == (200, {"commands_allowed": True, "reason": None})
        command = device.create_command(action="pump_on", duration=3)
        assert command["status"] == "pending"
        done = device.wait_status(command["command_id"], "applied", "rejected", "timeout")
        assert done["status"] == "applied"
        assert done["confirmed_relay_state"] == "on"


@pytest.mark.skipif(not PROXY, reason="E2E_PROXY_URL not set (Nginx /api proxy)")
def test_tunnel_headers_survive_the_nginx_proxy():
    with FakeDevice() as device:
        device.announce()
        status, body = call(
            PROXY, "POST", f"/devices/{device.device_id}/commands",
            {"action": "pump_on", "duration_seconds": 5}, CLOUDFLARE,
        )
        assert status == 403, body
        assert_nothing_published(device)
        assert call(PROXY, "GET", "/control-access", headers=CLOUDFLARE)[1]["commands_allowed"] is False
        # Without tunnel headers, the trusted Web path keeps control.
        assert call(PROXY, "GET", "/control-access")[1]["commands_allowed"] is True
