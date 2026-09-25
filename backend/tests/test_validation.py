import json

import pytest
from pydantic import ValidationError

from app.ingest import validate_message
from app.schemas import CommandCreate, PayloadError, parse_topic

TOPIC = "garden/node_01/telemetry"
COMMAND_ID = "3f0e6f5c-7b0a-4d65-9d8e-8c1f0b1f2a11"


def telemetry(**overrides):
    payload = {
        "schema": "telemetry-v1",
        "simulated": True,
        "device_id": "node_01",
        "boot_id": "boot_9c1f0b1f",
        "sequence": 1,
        "clock_synced": True,
        "measured_at": "2026-09-18T10:00:00.000Z",
        "uptime_ms": 12345,
        "temperature_c": 27.5,
        "air_humidity_pct": 60.1,
        "soil_moisture_pct": 42,
        "sensor_status": {"aht20": "ok", "soil": "ok"},
    }
    payload.update(overrides)
    return json.dumps(payload).encode()


def ack(**overrides):
    payload = {
        "schema": "ack-v1",
        "command_id": COMMAND_ID,
        "device_id": "node_01",
        "boot_id": "boot_9c1f0b1f",
        "status": "applied",
        "reason": None,
        "clock_synced": True,
        "acked_at": "2026-09-18T10:00:01.000Z",
    }
    payload.update(overrides)
    return json.dumps(payload).encode()


def state(**overrides):
    payload = {
        "schema": "state-v1",
        "device_id": "node_01",
        "boot_id": "boot_9c1f0b1f",
        "state_sequence": 12,
        "mode": "MANUAL",
        "relay_state": "on",
        "last_command_id": COMMAND_ID,
        "last_command_sequence": 7,
        "clock_synced": True,
        "reported_at": "2026-09-18T10:00:01.100Z",
        "uptime_ms": 12400,
    }
    payload.update(overrides)
    return json.dumps(payload).encode()


# --- telemetry -------------------------------------------------------------


def test_valid_telemetry_is_accepted():
    kind, model, raw = validate_message(TOPIC, telemetry())

    assert kind == "telemetry"
    assert model.device_id == "node_01"
    assert model.boot_id == "boot_9c1f0b1f"
    assert model.sequence == 1
    assert model.simulated is True
    assert model.soil_moisture_pct == 42.0
    assert model.sensor_status.aht20 == "ok"
    assert raw["schema"] == "telemetry-v1"


def test_unsynced_clock_requires_a_null_timestamp():
    _, model, _ = validate_message(
        TOPIC, telemetry(clock_synced=False, measured_at=None)
    )
    assert model.measured_at is None

    with pytest.raises(ValidationError):
        validate_message(TOPIC, telemetry(clock_synced=False))
    with pytest.raises(ValidationError):
        validate_message(TOPIC, telemetry(measured_at=None))


def test_sensor_error_is_reported_as_null_and_must_match_status():
    _, model, _ = validate_message(
        TOPIC,
        telemetry(
            temperature_c=None,
            air_humidity_pct=None,
            sensor_status={"aht20": "error", "soil": "ok"},
        ),
    )
    assert model.temperature_c is None
    assert model.sensor_status.aht20 == "error"

    for overrides in (
        {"temperature_c": None},
        {"soil_moisture_pct": None},
        {"sensor_status": {"aht20": "error", "soil": "ok"}},
        {
            "soil_moisture_pct": None,
            "sensor_status": {"aht20": "ok", "soil": "ok"},
        },
    ):
        with pytest.raises(ValidationError):
            validate_message(TOPIC, telemetry(**overrides))


@pytest.mark.parametrize(
    "payload",
    [b"{not json", b"", b"\xff\xfe", b"[1, 2]", b'"text"', b'{"temperature_c": NaN}'],
)
def test_malformed_json_raises_payload_error(payload):
    with pytest.raises(PayloadError):
        validate_message(TOPIC, payload)


@pytest.mark.parametrize(
    "overrides",
    [
        {"sequence": "1"},
        {"sequence": 0},
        {"sequence": True},
        {"boot_id": "boot/one"},
        {"boot_id": ""},
        {"uptime_ms": -1},
        {"simulated": "yes"},
        {"clock_synced": "yes"},
        {"temperature_c": "27"},
        {"temperature_c": True},
        {"air_humidity_pct": 101},
        {"soil_moisture_pct": -0.1},
        {"measured_at": "2026-09-18T10:00:00"},
        {"measured_at": "yesterday"},
        {"device_id": "node/01"},
        {"schema": ""},
        {"sensor_status": {"aht20": "broken", "soil": "ok"}},
        {"sensor_status": {"aht20": "ok"}},
    ],
)
def test_invalid_telemetry_fields_are_rejected(overrides):
    with pytest.raises(ValidationError):
            validate_message(TOPIC, telemetry(**overrides))


def test_payload_schema_is_fixed_for_each_topic():
    for topic, payload in (
        (TOPIC, telemetry(schema="telemetry-v2")),
        ("garden/node_01/ack", ack(schema="telemetry-v1")),
        ("garden/node_01/state", state(schema="ack-v1")),
    ):
        with pytest.raises(ValidationError):
            validate_message(topic, payload)


def test_missing_required_key_is_rejected():
    for key in ("boot_id", "uptime_ms", "sensor_status", "clock_synced", "sequence"):
        payload = json.loads(telemetry())
        del payload[key]
        with pytest.raises(ValidationError):
            validate_message(TOPIC, json.dumps(payload).encode())


def test_device_id_must_match_topic():
    with pytest.raises(PayloadError, match="device_id_mismatch_topic"):
        validate_message("garden/node_02/telemetry", telemetry())


@pytest.mark.parametrize(
    "topic",
    [
        "garden/node_01/control",
        "garden/node_01",
        "other/node_01/telemetry",
        "garden/a b/ack",
    ],
)
def test_unsupported_topics_are_rejected(topic):
    with pytest.raises(PayloadError):
        parse_topic(topic)


# --- ack and state ---------------------------------------------------------


def test_valid_ack_and_state():
    kind, model, _ = validate_message("garden/node_01/ack", ack())
    assert kind == "ack" and str(model.command_id) == COMMAND_ID
    assert model.boot_id == "boot_9c1f0b1f"

    kind, model, _ = validate_message("garden/node_01/state", state())
    assert kind == "state"
    assert model.relay_state == "on" and model.mode == "MANUAL"
    assert model.state_sequence == 12


@pytest.mark.parametrize(
    "overrides",
    [
        {"status": "done"},
        {"boot_id": "boot/one"},
        {"command_id": "not-a-uuid"},
        {"clock_synced": False},  # acked_at must then be null
        {"reason": "x" * 65},
    ],
)
def test_invalid_ack_is_rejected(overrides):
    with pytest.raises(ValidationError):
        validate_message("garden/node_01/ack", ack(**overrides))


def test_ack_without_a_clock_has_no_timestamp():
    _, model, _ = validate_message(
        "garden/node_01/ack", ack(clock_synced=False, acked_at=None)
    )
    assert model.acked_at is None

    with pytest.raises(ValidationError):
        validate_message("garden/node_01/ack", ack(acked_at=None))


def test_ack_reason_matches_rejected_status():
    _, model, _ = validate_message(
        "garden/node_01/ack", ack(status="rejected", reason="relay_error")
    )
    assert model.reason == "relay_error"

    for overrides in (
        {"status": "rejected", "reason": None},
        {"status": "applied", "reason": "relay_error"},
        {"status": "rejected", "reason": "not_a_contract_reason"},
    ):
        with pytest.raises(ValidationError):
            validate_message("garden/node_01/ack", ack(**overrides))


@pytest.mark.parametrize(
    "overrides",
    [
        {"relay_state": "ON"},
        {"relay_state": None},
        {"mode": "auto"},
        {"state_sequence": 0},
        {"state_sequence": "12"},
        {"clock_synced": False},  # reported_at must then be null
        {"last_command_sequence": 0},
    ],
)
def test_invalid_state_is_rejected(overrides):
    with pytest.raises(ValidationError):
        validate_message("garden/node_01/state", state(**overrides))


def test_state_without_a_last_command():
    _, model, _ = validate_message(
        "garden/node_01/state",
        state(last_command_id=None, last_command_sequence=None),
    )
    assert model.last_command_id is None

    for overrides in (
        {"last_command_id": None, "last_command_sequence": 7},
        {"last_command_id": COMMAND_ID, "last_command_sequence": None},
        {"reported_at": None},
    ):
        with pytest.raises(ValidationError):
            validate_message("garden/node_01/state", state(**overrides))


# --- command requests ------------------------------------------------------


def test_command_body_rules():
    assert CommandCreate(action="pump_on", duration_seconds=10).duration_seconds == 10
    assert CommandCreate(action="pump_off").duration_seconds is None
    for body in (
        {"action": "pump_on"},
        {"action": "pump_off", "duration_seconds": 5},
        {"action": "pump_on", "duration_seconds": 0},
        {"action": "pump_on", "duration_seconds": "5"},
        {"action": "explode"},
        {"action": "pump_off", "extra": 1},
    ):
        with pytest.raises(ValidationError):
            CommandCreate.model_validate(body)
