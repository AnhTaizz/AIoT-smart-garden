"""BC-02 against the real stack: PostgreSQL sessions, Mosquitto, FastAPI, Nginx.

E2E_PROXY_URL (the dashboard `/api` proxy) covers the Web/tunnel path. The
stack must run with CHAT_API_URL unset for the not-configured chat check.
"""

import hashlib
import os
import queue

import pytest

from helpers import (
    API,
    FakeDevice,
    auth_headers,
    db_connection,
    login,
    raw_request,
    request,
)

pytestmark = pytest.mark.skipif(not API, reason="E2E_API_BASE_URL not set")
PROXY = os.getenv("E2E_PROXY_URL", "").rstrip("/")
# What Cloudflare adds to a request that crossed a Quick Tunnel.
TUNNEL = {"Cf-Connecting-Ip": "1.1.1.1", "Cf-Ray": "8f00e2e000000000-SIN", "X-Forwarded-For": "1.1.1.1"}
ON = {"action": "pump_on", "duration_seconds": 3}


def bases():
    return [API] + ([PROXY] if PROXY else [])


def new_session():
    status, body = login()
    assert status == 200, body
    return body["access_token"], {"Authorization": f"Bearer {body['access_token']}"}


def assert_nothing_published(device):
    with pytest.raises(queue.Empty):
        device.control.get(timeout=1.5)
    assert request("GET", f"/devices/{device.device_id}/commands")[1]["count"] == 0


@pytest.mark.parametrize("base", bases())
def test_anonymous_pump_on_is_401_not_stored_not_published(base):
    with FakeDevice() as device:
        device.announce()
        for headers in ({}, TUNNEL, {"Authorization": "Bearer forged-token"}):
            status, body = raw_request(
                "POST", f"{base}/devices/{device.device_id}/commands", ON, headers,
            )
            assert status == 401, body
        assert_nothing_published(device)
        assert device.state()["relay_state"] == "off"


@pytest.mark.parametrize("base", bases())
def test_anonymous_cannot_read_garden_data(base):
    with FakeDevice() as device:
        device.announce()
        device.publish_telemetry()
        device.wait_for_count(1)
        for path in ("latest", "telemetry", "state", "commands"):
            status, _ = raw_request("GET", f"{base}/devices/{device.device_id}/{path}")
            assert status == 401, path
        assert raw_request("GET", f"{base}/control-access")[0] == 401
        assert raw_request("POST", f"{base}/chat", {"message": "Xin chào"})[0] == 401
    # Liveness stays public and minimal.
    assert raw_request("GET", f"{API}/health") == (200, {"status": "ok"})


@pytest.mark.parametrize("base", bases())
@pytest.mark.parametrize("tunnel", [False, True])
def test_operator_command_completes_g02_lifecycle(base, tunnel):
    headers = {**auth_headers(), **(TUNNEL if tunnel else {})}
    with FakeDevice(auto_respond=True) as device:
        device.announce()
        assert raw_request("GET", f"{base}/control-access", headers=headers)[1] == {
            "commands_allowed": True, "reason": None, "role": "operator",
        }
        status, created = raw_request(
            "POST", f"{base}/devices/{device.device_id}/commands", ON, headers,
        )
        assert status == 202 and created["status"] == "pending"
        assert created["target_boot_id"] == device.boot_id
        done = device.wait_status(created["command_id"], "applied", "rejected", "timeout")
        assert done["status"] == "applied"
        assert done["device_ack"] == "applied" and done["confirmed_relay_state"] == "on"
        sent = device.next_control(created["command_id"])
        assert sent["command_sequence"] == created["command_sequence"]
        assert sent["expires_at"] and sent["target_boot_id"] == device.boot_id


def test_logout_and_expiry_block_new_commands():
    with FakeDevice() as device:
        device.announce()
        token, headers = new_session()
        assert request("GET", "/auth/me", auth=False, headers=headers)[0] == 200
        # Expire this session in PostgreSQL: the server-side check must refuse it.
        with db_connection() as conn:
            conn.execute(
                "UPDATE auth_session SET expires_at = now() - interval '1 second'"
                " WHERE token_hash = %s",
                (hashlib.sha256(token.encode()).digest(),),
            )
        status, body = request(
            "POST", f"/devices/{device.device_id}/commands", ON, headers=headers, auth=False,
        )
        assert status == 401 and body["detail"]["code"] == "invalid_session"

        token, headers = new_session()
        assert request("POST", "/auth/logout", headers=headers, auth=False)[0] == 200
        status, _ = request(
            "POST", f"/devices/{device.device_id}/commands", ON, headers=headers, auth=False,
        )
        assert status == 401
        assert_nothing_published(device)


def test_session_table_never_holds_the_raw_token():
    token, _ = new_session()
    with db_connection() as conn:
        raw = conn.execute(
            "SELECT count(*) FROM auth_session WHERE token_hash = %s", (token.encode(),)
        ).fetchone()[0]
        hashed = conn.execute(
            "SELECT count(*) FROM auth_session WHERE token_hash = %s",
            (hashlib.sha256(token.encode()).digest(),),
        ).fetchone()[0]
    assert (raw, hashed) == (0, 1)


def test_wrong_password_is_401():
    status, body = login(password="definitely-not-the-password")
    assert status == 401 and body["detail"]["code"] == "invalid_credentials"
    # The shared session keeps working (one failure, below the lockout).
    assert request("GET", "/auth/me")[0] == 200


def test_pump_on_limit_never_blocks_pump_off():
    with FakeDevice() as device:
        device.announce()
        statuses = []
        for _ in range(20):
            status, body = request("POST", f"/devices/{device.device_id}/commands", ON)
            statuses.append(status)
            if status == 429:
                assert body["detail"]["code"] == "command_rate_limited"
                break
        assert statuses[-1] == 429, statuses
        assert set(statuses[:-1]) == {202}
        status, off = request("POST", f"/devices/{device.device_id}/commands", {"action": "pump_off"})
        assert status == 202 and off["status"] == "pending"


@pytest.mark.parametrize("base", bases())
def test_unconfigured_chat_is_a_clear_503_without_old_ngrok(base):
    status, body = raw_request(
        "POST", f"{base}/chat", {"message": "Xin chào", "include_garden_context": False},
        auth_headers(),
    )
    assert status == 503, body
    detail = body["detail"]
    assert detail["code"] == "chat_unavailable" and detail["reason"] == "not_configured"
    assert "ngrok" not in detail["message"]
