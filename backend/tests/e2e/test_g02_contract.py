"""Regression tests for the G02 contract rules (draft, pending team sign-off).

These cover the rules that were wrong or missing in the first backend pass:
per-command state evidence, boot handling across reboots, command ordering
with command_sequence, telemetry v1 validation and the REST error envelope.
"""

import pytest

from helpers import (
    API,
    FakeDevice,
    db_connection,
    error_code,
    expires_in,
    request,
    wait_for,
)

pytestmark = pytest.mark.skipif(not API, reason="E2E_API_BASE_URL not set")


@pytest.fixture
def device():
    with FakeDevice() as fake:
        yield fake


# --- applied needs ACK *and* matching state evidence -----------------------


def test_ack_applied_alone_does_not_confirm_command(device):
    device.announce()
    command = device.create_command(duration=5)
    device.next_control(command["command_id"])
    device.publish_ack(command["command_id"], "applied")

    # The device claims success but never reported relay_state=on.
    final = device.wait_status(command["command_id"], "timeout", "applied")
    assert final["status"] == "timeout", "ACK alone must not prove the pump ran"
    assert final["device_ack"] == "applied"
    assert final["state_confirmed_at"] is None


def test_state_off_alone_does_not_confirm_pump_on(device):
    device.announce()
    command = device.create_command(duration=5)
    device.next_control(command["command_id"])
    device.publish_ack(command["command_id"], "applied")
    # Relay off contradicts pump_on, so it is not evidence for this command.
    device.publish_state(relay_state="off", last_command_id=command["command_id"])

    final = device.wait_status(command["command_id"], "timeout", "applied")
    assert final["status"] == "timeout"
    assert final["confirmed_relay_state"] is None


def test_pump_on_applied_then_auto_off_stays_applied(device):
    device.announce()
    command = device.create_command(duration=5)
    control = device.next_control(command["command_id"])
    device.publish_ack(command["command_id"], "applied")
    device.publish_state(
        relay_state="on",
        last_command_id=command["command_id"],
        last_command_sequence=control["command_sequence"],
    )

    applied = device.wait_status(command["command_id"], "applied")
    assert applied["confirmed_relay_state"] == "on"

    # Pump stops by itself after the duration: evidence must survive.
    device.publish_state(
        relay_state="off",
        last_command_id=command["command_id"],
        last_command_sequence=control["command_sequence"],
    )
    wait_for(lambda: device.state()["relay_state"] == "off")
    still = device.command(command["command_id"])
    assert still["status"] == "applied"
    assert still["confirmed_relay_state"] == "on"


def test_state_before_ack_is_also_valid_evidence(device):
    device.announce()
    command = device.create_command(duration=5)
    device.next_control(command["command_id"])
    device.publish_state(relay_state="on", last_command_id=command["command_id"])
    assert device.command(command["command_id"])["status"] == "pending"

    device.publish_ack(command["command_id"], "applied")
    applied = device.wait_status(command["command_id"], "applied")
    assert applied["confirmed_relay_state"] == "on"


def test_applied_ack_cannot_be_downgraded_by_repeated_accepted(device):
    device.announce()
    command = device.create_command(duration=5)
    control = device.next_control(command["command_id"])
    device.publish_ack(command["command_id"], "applied")
    device.wait_for_ack(command["command_id"], "applied")

    device.publish_ack(command["command_id"], "accepted")
    wait_for(lambda: _ack_event_count(command["command_id"], "accepted") == 1)
    assert device.command(command["command_id"])["device_ack"] == "applied"

    device.publish_state(
        relay_state="on",
        last_command_id=command["command_id"],
        last_command_sequence=control["command_sequence"],
    )
    assert device.wait_status(command["command_id"], "applied", timeout=5)[
        "status"
    ] == "applied"


def test_repeated_accepted_before_applied_is_monotonic(device):
    device.announce()
    command = device.create_command(duration=5)
    control = device.next_control(command["command_id"])

    for _ in range(3):
        device.publish_ack(command["command_id"], "accepted")
    wait_for(lambda: _ack_event_count(command["command_id"], "accepted") == 3)
    assert device.command(command["command_id"])["device_ack"] == "accepted"

    device.publish_ack(command["command_id"], "applied")
    device.publish_state(
        relay_state="on",
        last_command_id=command["command_id"],
        last_command_sequence=control["command_sequence"],
    )
    assert device.wait_status(command["command_id"], "applied")["status"] == "applied"


def test_accepted_from_wrong_boot_does_not_replace_applied_evidence(device):
    device.announce()
    command = device.create_command(duration=5)
    control = device.next_control(command["command_id"])
    device.publish_ack(command["command_id"], "applied")
    device.wait_for_ack(command["command_id"], "applied")

    device.publish_ack(
        command["command_id"], "accepted", boot_id="boot_wrong_but_valid"
    )
    wait_for(lambda: _ack_outcome_count(command["command_id"], "stale_boot") == 1)
    unchanged = device.command(command["command_id"])
    assert unchanged["device_ack"] == "applied"
    assert unchanged["ack_boot_id"] == device.boot_id

    device.publish_state(
        relay_state="on",
        last_command_id=command["command_id"],
        last_command_sequence=control["command_sequence"],
    )
    assert device.wait_status(command["command_id"], "applied")["status"] == "applied"


def test_repeated_ack_does_not_change_final_statuses(device):
    device.announce()

    applied = device.create_command(duration=5)
    applied_control = device.next_control(applied["command_id"])
    device.publish_ack(applied["command_id"], "applied")
    device.publish_state(
        relay_state="on",
        last_command_id=applied["command_id"],
        last_command_sequence=applied_control["command_sequence"],
    )
    device.wait_status(applied["command_id"], "applied")
    device.publish_ack(applied["command_id"], "accepted")

    rejected = device.create_command(action="pump_off", duration=None)
    device.next_control(rejected["command_id"])
    device.publish_ack(rejected["command_id"], "rejected", reason="relay_error")
    device.wait_status(rejected["command_id"], "rejected")
    device.publish_ack(rejected["command_id"], "accepted")

    timed_out = device.create_command(action="pump_off", duration=None)
    device.next_control(timed_out["command_id"])
    with db_connection() as conn:
        conn.execute(
            "UPDATE command SET status = 'timeout', finalized_at = expires_at"
            " WHERE command_id = %s",
            (timed_out["command_id"],),
        )
    device.publish_ack(timed_out["command_id"], "accepted")

    wait_for(lambda: _ack_event_count(applied["command_id"], "accepted") == 1)
    wait_for(lambda: _ack_event_count(rejected["command_id"], "accepted") == 1)
    wait_for(lambda: _ack_event_count(timed_out["command_id"], "accepted") == 1)
    assert device.command(applied["command_id"])["status"] == "applied"
    assert device.command(rejected["command_id"])["status"] == "rejected"
    assert device.command(timed_out["command_id"])["status"] == "timeout"


def test_pump_off_confirmed_by_relay_off_state(device):
    device.announce(relay_state="on")
    command = device.create_command(action="pump_off", duration=None)
    device.next_control(command["command_id"])
    device.publish_ack(command["command_id"], "applied")
    device.publish_state(relay_state="off", last_command_id=command["command_id"])

    applied = device.wait_status(command["command_id"], "applied")
    assert applied["confirmed_relay_state"] == "off"


def test_late_evidence_never_flips_timeout_to_applied(device):
    device.announce()
    command = device.create_command(duration=5)
    device.next_control(command["command_id"])
    timed_out = device.wait_status(
        command["command_id"], "timeout", timeout=max(expires_in(command), 0) + 8
    )
    assert timed_out["status"] == "timeout"

    device.publish_ack(command["command_id"], "applied")
    device.publish_state(relay_state="on", last_command_id=command["command_id"])
    late = wait_for(
        lambda: (
            (c := device.command(command["command_id"]))["late_ack"]
            and c["confirmed_relay_state"] == "on"
            and c
        )
    )
    assert late["status"] == "timeout"
    assert late["late_ack"] == "applied"
    assert late["confirmed_boot_id"] == device.boot_id
    assert late["state_confirmed_at"] is not None
    # A valid state still updates the device, even after the command expired.
    wait_for(lambda: device.state()["relay_state"] == "on")


def test_device_answering_before_the_post_returns_still_confirms(device):
    """A fast device ACKs before POST /commands has committed its row."""
    with FakeDevice(device_id=device.device_id, boot_id=device.boot_id, auto_respond=True) as fast:
        fast.announce()
        command = fast.create_command(duration=5)
        applied = fast.wait_status(command["command_id"], "applied", timeout=12)

    assert applied["device_ack"] == "applied", "the ACK must not be lost in a race"
    assert applied["confirmed_relay_state"] == "on"

    # The command row must be committed before the control message goes out,
    # otherwise an ACK that arrives first is dropped as an unknown command.
    with db_connection() as conn:
        lost = conn.execute(
            "SELECT count(*) FROM command_event WHERE command_id = %s"
            " AND outcome = 'unknown_command'",
            (command["command_id"],),
        ).fetchone()[0]
    assert lost == 0, "an ACK was dropped because the command was not committed yet"


# --- state ordering --------------------------------------------------------


def test_old_state_is_evidence_but_does_not_overwrite_newer_state(device):
    device.announce()
    command = device.create_command(duration=5)
    device.next_control(command["command_id"])
    device.publish_ack(command["command_id"], "applied")

    # Newest state first (sequence 9), then an older one (sequence 5).
    device.publish_state(relay_state="off", state_sequence=9)
    wait_for(lambda: device.state()["state_sequence"] == 9)
    device.publish_state(
        relay_state="on", state_sequence=5, last_command_id=command["command_id"]
    )

    applied = device.wait_status(command["command_id"], "applied")
    assert applied["confirmed_relay_state"] == "on"
    current = device.state()
    assert current["state_sequence"] == 9, "device state must not go backwards"
    assert current["relay_state"] == "off"


# --- boots and reboots -----------------------------------------------------


def test_pump_on_requires_a_known_boot(device):
    status, body = request(
        "POST",
        f"/devices/{device.device_id}/commands",
        {"action": "pump_on", "duration_seconds": 5},
    )
    assert status == 409, (status, body)
    assert error_code(body) == "device_boot_unknown"

    # pump_off is boot-agnostic and stays allowed.
    off = device.create_command(action="pump_off", duration=None)
    assert off["target_boot_id"] is None


def test_reboot_finalizes_pending_commands_of_the_old_boot(device):
    device.announce()
    old_boot = device.boot_id
    command = device.create_command(duration=5)
    device.next_control(command["command_id"])
    assert command["target_boot_id"] == old_boot

    device.reboot()
    device.announce()

    rebooted = device.wait_status(command["command_id"], "timeout")
    assert rebooted["reason"] == "backend:device_rebooted"

    # An ACK from the boot that died must not resurrect the command.
    device.publish_ack(command["command_id"], "applied", boot_id=old_boot)
    device.publish_state(
        relay_state="on", boot_id=old_boot, last_command_id=command["command_id"]
    )
    wait_for(
        lambda: (c := device.command(command["command_id"]))["late_ack"] == "applied" and c
    )
    assert device.command(command["command_id"])["status"] == "timeout"
    assert device.state()["boot_id"] == device.boot_id, "state must not fall back"


def test_pending_pump_off_survives_a_reboot(device):
    device.announce()
    command = device.create_command(action="pump_off", duration=None)
    device.next_control(command["command_id"])
    device.reboot()
    device.announce()
    assert device.command(command["command_id"])["status"] == "pending"

    device.publish_ack(command["command_id"], "applied")
    device.publish_state(relay_state="off", last_command_id=command["command_id"])
    assert device.wait_status(command["command_id"], "applied")["status"] == "applied"


def test_ack_from_an_older_boot_is_ignored(device):
    device.announce()
    old_boot = device.boot_id
    device.reboot()
    device.announce()
    command = device.create_command(duration=5)
    device.next_control(command["command_id"])

    device.publish_ack(command["command_id"], "applied", boot_id=old_boot)
    device.publish_state(
        relay_state="on", boot_id=old_boot, last_command_id=command["command_id"]
    )
    final = device.wait_status(
        command["command_id"], "timeout", "applied", timeout=max(expires_in(command), 0) + 8
    )
    assert final["status"] == "timeout", "evidence from a dead boot must not apply"


# --- command ordering ------------------------------------------------------


def test_command_sequence_is_per_device_monotonic_and_persisted(device):
    device.announce()
    first = device.next_control(device.create_command(duration=5)["command_id"])
    second = device.next_control(
        device.create_command(action="pump_off", duration=None)["command_id"]
    )
    assert second["command_sequence"] == first["command_sequence"] + 1

    with db_connection() as conn:
        stored = conn.execute(
            "SELECT last_sequence FROM device_command_counter WHERE device_id = %s",
            (device.device_id,),
        ).fetchone()
    assert stored is not None, "the counter must live in PostgreSQL, not in memory"
    assert stored[0] == second["command_sequence"]


def test_control_payload_carries_the_ordering_fields(device):
    device.announce()
    command = device.create_command(duration=7)
    control = device.next_control(command["command_id"])
    assert set(control) == {
        "schema",
        "command_id",
        "device_id",
        "command_sequence",
        "action",
        "params",
        "target_boot_id",
        "issued_at",
        "expires_at",
    }
    assert control["schema"] == "command-v1"
    assert control["params"] == {"duration_seconds": 7}
    assert "ttl_seconds" not in control


# --- telemetry v1 ----------------------------------------------------------


def test_duplicate_telemetry_is_ignored_without_being_rejected(device):
    payload = device.publish_telemetry(sequence=1)
    wait_for(lambda: device.history(limit=10)["count"] == 1)
    device.publish_telemetry(raw=payload)
    device.publish_telemetry(sequence=2)
    wait_for(lambda: device.history(limit=10)["count"] == 2)

    with db_connection() as conn:
        rejected = conn.execute(
            "SELECT count(*) FROM rejected_message WHERE topic = %s",
            (f"garden/{device.device_id}/telemetry",),
        ).fetchone()[0]
    assert rejected == 0, "a duplicate is not an invalid payload"


def test_unsynced_clock_telemetry_must_not_carry_a_timestamp(device):
    device.publish_telemetry(sequence=1, clock_synced=False, measured_at=None)
    stored = wait_for(lambda: device.history(limit=5)["count"] == 1 and device.history(limit=5))
    assert stored["items"][0]["measured_at"] is None
    assert stored["items"][0]["clock_synced"] is False

    # Claiming an unsynced clock while sending a timestamp is contradictory.
    device.publish_telemetry(sequence=2, clock_synced=False)
    wait_for(
        lambda: any(
            "clock" in reason or "measured_at" in reason
            for reason in _reasons(device.device_id)
        ),
        message="contradictory clock_synced payload was not rejected",
    )
    assert device.history(limit=5)["count"] == 1


def test_sensor_status_must_match_null_readings(device):
    device.publish_telemetry(sequence=1, temperature_c=None)
    wait_for(
        lambda: any("sensor_status" in reason for reason in _reasons(device.device_id)),
        message="null reading with sensor_status ok was not rejected",
    )
    device.publish_telemetry(
        sequence=2,
        temperature_c=None,
        air_humidity_pct=None,
        sensor_status={"aht20": "error", "soil": "ok"},
    )
    stored = wait_for(lambda: device.history(limit=5)["count"] == 1 and device.history(limit=5))
    item = stored["items"][0]
    assert item["temperature_c"] is None
    assert item["sensor_status"] == {"aht20": "error", "soil": "ok"}


def _reasons(device_id):
    with db_connection() as conn:
        return [
            row[0]
            for row in conn.execute(
                "SELECT reason FROM rejected_message WHERE topic = %s ORDER BY id",
                (f"garden/{device_id}/telemetry",),
            ).fetchall()
        ]


def _ack_event_count(command_id, ack_status):
    with db_connection() as conn:
        return conn.execute(
            "SELECT count(*) FROM command_event WHERE command_id = %s"
            " AND kind = 'ack' AND ack_status = %s",
            (command_id, ack_status),
        ).fetchone()[0]


def _ack_outcome_count(command_id, outcome):
    with db_connection() as conn:
        return conn.execute(
            "SELECT count(*) FROM command_event WHERE command_id = %s"
            " AND kind = 'ack' AND outcome = %s",
            (command_id, outcome),
        ).fetchone()[0]


# --- REST shape ------------------------------------------------------------


def test_error_bodies_share_one_shape(device):
    checks = [
        ("GET", f"/devices/{device.device_id}/latest", None, 404, "no_telemetry"),
        ("GET", f"/devices/{device.device_id}/state", None, 404, "no_state"),
        (
            "POST",
            f"/devices/{device.device_id}/commands",
            {"action": "pump_on"},
            422,
            "invalid_payload",
        ),
        (
            "POST",
            f"/devices/{device.device_id}/commands",
            {"action": "fly"},
            422,
            "invalid_payload",
        ),
        ("GET", "/commands/not-a-uuid", None, 422, "invalid_payload"),
    ]
    for method, path, body, expected_status, expected_code in checks:
        status, payload = request(method, path, body)
        assert status == expected_status, (path, status, payload)
        assert error_code(payload) == expected_code, (path, payload)
        assert isinstance(payload["detail"].get("message"), str)


def test_command_list_is_wrapped(device):
    device.announce()
    device.create_command(action="pump_off", duration=None)
    status, body = request("GET", f"/devices/{device.device_id}/commands?limit=5")
    assert status == 200
    assert body["count"] == len(body["items"]) == 1
    assert body["items"][0]["command_sequence"] >= 1
