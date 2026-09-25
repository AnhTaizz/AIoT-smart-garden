"""B-W1 acceptance checks against a running stack (API + Mosquitto + PostgreSQL).

Skipped unless E2E_API_BASE_URL is set. See backend/README.md for how to run.
The G02 rules added later live in test_g02_contract.py.
"""

import pytest

from helpers import API, FakeDevice, db_connection, error_code, expires_in, request

pytestmark = pytest.mark.skipif(not API, reason="E2E_API_BASE_URL not set")


@pytest.fixture
def device():
    with FakeDevice() as fake:
        yield fake


# --- B-W1-01: telemetry into PostgreSQL ------------------------------------


def test_ten_telemetry_messages_are_stored_and_queryable(device):
    for _ in range(10):
        device.publish_telemetry()

    body = device.wait_for_count(10)
    assert [item["sequence"] for item in body["items"]] == list(range(1, 11))
    assert {item["device_id"] for item in body["items"]} == {device.device_id}
    assert all(item["simulated"] is True for item in body["items"])
    assert all(item["boot_id"] == device.boot_id for item in body["items"])

    newest_first = device.history(limit=3, order="desc")
    assert [item["sequence"] for item in newest_first["items"]] == [10, 9, 8]

    status, latest = device.latest()
    assert status == 200
    assert latest["sequence"] == 10 and latest["stale"] is False
    assert latest["stale_after_seconds"] >= 1

    with db_connection() as conn:
        rows = conn.execute(
            "SELECT sequence FROM telemetry WHERE device_id = %s ORDER BY sequence",
            (device.device_id,),
        ).fetchall()
    assert [row[0] for row in rows] == list(range(1, 11))


def test_invalid_messages_are_rejected_and_the_subscriber_keeps_running(device):
    device.publish_telemetry(raw=b"{not json")
    device.publish_telemetry(raw=b"\xff\xfe")
    device.publish_telemetry(sequence=500, air_humidity_pct=250)
    device.publish_telemetry(sequence=501, device_id="someone_else")
    device.publish_telemetry(sequence=99)

    body = device.wait_for_count(1)
    assert [item["sequence"] for item in body["items"]] == [99]

    reasons = _reasons(device.device_id)
    assert reasons[:2] == ["invalid_json", "invalid_json"]
    assert any("air_humidity_pct" in reason for reason in reasons)
    assert "device_id_mismatch_topic" in reasons


def test_unknown_device_and_bad_device_id(device):
    status, body = device.latest()
    assert status == 404 and error_code(body) == "no_telemetry"
    assert request("GET", "/devices/bad%2Fid/latest")[0] in (404, 422)


def _reasons(device_id):
    with db_connection() as conn:
        return [
            row[0]
            for row in conn.execute(
                "SELECT reason FROM rejected_message WHERE topic = %s ORDER BY id",
                (f"garden/{device_id}/telemetry",),
            ).fetchall()
        ]


# --- B-W1-02: command lifecycle -------------------------------------------


def test_command_applied_only_after_ack_and_state(device):
    device.announce()
    command = device.create_command(duration=5)
    control = device.next_control(command["command_id"])
    assert control["action"] == "pump_on"
    assert control["params"] == {"duration_seconds": 5}
    assert control["target_boot_id"] == device.boot_id

    # HTTP 202 is not success: still pending until the device proves it acted.
    assert device.command(command["command_id"])["status"] == "pending"

    device.publish_ack(command["command_id"], "accepted")
    accepted = device.wait_for_ack(command["command_id"], "accepted")
    assert accepted["status"] == "pending"

    device.publish_ack(command["command_id"], "applied")
    device.publish_state(relay_state="on", last_command_id=command["command_id"])
    applied = device.wait_status(command["command_id"], "applied")
    assert applied["device_ack"] == "applied"
    assert applied["confirmed_relay_state"] == "on"

    state = device.state()
    assert state["relay_state"] == "on"
    assert state["last_command_id"] == command["command_id"]

    listed = request("GET", f"/devices/{device.device_id}/commands")[1]
    assert listed["items"][0]["command_id"] == command["command_id"]


def test_command_rejected_keeps_the_device_reason(device):
    device.announce()
    command = device.create_command(action="pump_off", duration=None)
    device.next_control(command["command_id"])
    device.publish_ack(command["command_id"], "rejected", reason="relay_error")

    rejected = device.wait_status(command["command_id"], "rejected")
    assert rejected["reason"] == "relay_error"
    assert rejected["device_ack"] == "rejected"


def test_command_times_out_without_any_answer(device):
    device.announce()
    command = device.create_command(duration=5)
    device.next_control(command["command_id"])

    timed_out = device.wait_status(
        command["command_id"], "timeout", timeout=max(expires_in(command), 0) + 8
    )
    assert timed_out["status"] == "timeout"
    assert timed_out["late_ack"] is None
    assert timed_out["state_confirmed_at"] is None


def test_invalid_command_requests(device):
    device.announce()
    checks = [
        ({"action": "pump_on"}, 422),
        ({"action": "pump_on", "duration_seconds": 100000}, 422),
        ({"action": "pump_off", "duration_seconds": 5}, 422),
        ({"action": "open_valve"}, 422),
    ]
    for body, expected in checks:
        status, payload = request(
            "POST", f"/devices/{device.device_id}/commands", body
        )
        assert status == expected, (body, status, payload)
        assert error_code(payload) == "invalid_payload"

    status, payload = request("GET", "/commands/00000000-0000-4000-8000-000000000000")
    assert status == 404 and error_code(payload) == "command_not_found"
