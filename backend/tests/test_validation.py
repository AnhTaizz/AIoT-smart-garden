import json

import pytest
from pydantic import ValidationError

from app.ingest import validate_message
from app.schemas import CommandCreate, PayloadError, parse_topic

TOPIC = "garden/node_01/telemetry"


def telemetry(**overrides):
    payload = {
        "schema": "bootstrap-telemetry-v0",
        "simulated": True,
        "device_id": "node_01",
        "sequence": 1,
        "measured_at": "2026-09-18T10:00:00.000Z",
        "temperature_c": 27.5,
        "air_humidity_pct": 60.1,
        "soil_moisture_pct": 42,
    }
    payload.update(overrides)
    return json.dumps(payload).encode()


def test_valid_simulator_payload_is_accepted():
    kind, model, raw = validate_message(TOPIC, telemetry())
    assert kind == "telemetry"
    assert model.device_id == "node_01"
    assert model.sequence == 1
    assert model.simulated is True
    assert model.soil_moisture_pct == 42.0
    assert raw["schema"] == "bootstrap-telemetry-v0"


def test_null_sensor_value_is_kept_as_null_not_zero():
    _, model, _ = validate_message(TOPIC, telemetry(temperature_c=None))
    assert model.temperature_c is None


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
        {"sequence": -1},
        {"sequence": True},
        {"simulated": "yes"},
        {"temperature_c": "27"},
        {"temperature_c": True},
        {"air_humidity_pct": 101},
        {"soil_moisture_pct": -0.1},
        {"measured_at": "2026-09-18T10:00:00"},
        {"measured_at": "yesterday"},
        {"device_id": "node/01"},
        {"schema": ""},
    ],
)
def test_invalid_fields_raise_validation_error(overrides):
    with pytest.raises(ValidationError):
        validate_message(TOPIC, telemetry(**overrides))


def test_missing_sensor_key_is_rejected():
    payload = json.loads(telemetry())
    del payload["soil_moisture_pct"]
    with pytest.raises(ValidationError):
        validate_message(TOPIC, json.dumps(payload).encode())


def test_device_id_must_match_topic():
    with pytest.raises(PayloadError, match="device_id_mismatch_topic"):
        validate_message("garden/node_02/telemetry", telemetry())


@pytest.mark.parametrize(
    "topic",
    ["garden/node_01/control", "garden/node_01", "other/node_01/telemetry", "garden/a b/ack"],
)
def test_unsupported_topics_are_rejected(topic):
    with pytest.raises(PayloadError):
        parse_topic(topic)


def test_ack_and_state_payloads():
    command_id = "3f0e6f5c-7b0a-4d65-9d8e-8c1f0b1f2a11"
    kind, ack, _ = validate_message(
        "garden/node_01/ack",
        json.dumps(
            {"command_id": command_id, "device_id": "node_01", "status": "applied"}
        ).encode(),
    )
    assert kind == "ack" and str(ack.command_id) == command_id

    with pytest.raises(ValidationError):
        validate_message(
            "garden/node_01/ack",
            json.dumps(
                {"command_id": command_id, "device_id": "node_01", "status": "done"}
            ).encode(),
        )

    kind, state, _ = validate_message(
        "garden/node_01/state",
        json.dumps(
            {"device_id": "node_01", "relay_state": "on", "last_command_id": command_id}
        ).encode(),
    )
    assert kind == "state" and state.relay_state == "on"


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
