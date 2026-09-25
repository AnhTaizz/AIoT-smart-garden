"""End-to-end checks against a running stack (API + Mosquitto + PostgreSQL).

Skipped unless E2E_API_BASE_URL is set. See backend/README.md for how to run.
Each run uses a fresh device_id so it never mixes with demo data.
"""

import json
import os
import queue
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone

import psycopg
import pytest
from paho.mqtt import client as mqtt

API = os.getenv("E2E_API_BASE_URL", "").rstrip("/")
MQTT_HOST = os.getenv("E2E_MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("E2E_MQTT_PORT", "1883"))

pytestmark = pytest.mark.skipif(not API, reason="E2E_API_BASE_URL not set")

DEVICE = f"e2e_{uuid.uuid4().hex[:8]}"


def request(method, path, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        API + path, data=data, method=method, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status, json.loads(response.read() or b"null")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"null")


def wait_for(predicate, timeout=10.0, interval=0.2):
    deadline = time.monotonic() + timeout
    while True:
        value = predicate()
        if value:
            return value
        if time.monotonic() > deadline:
            raise AssertionError("condition not met before timeout")
        time.sleep(interval)


@pytest.fixture(scope="module")
def mqtt_client():
    received: "queue.Queue[tuple[str, dict]]" = queue.Queue()
    connected = queue.Queue()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"{DEVICE}-test")
    client.on_connect = lambda c, u, f, rc, p: connected.put(rc)
    client.on_message = lambda c, u, m: received.put((m.topic, json.loads(m.payload)))
    client.connect(MQTT_HOST, MQTT_PORT)
    client.loop_start()
    assert connected.get(timeout=5) == 0
    client.subscribe(f"garden/{DEVICE}/control", qos=1)
    client.received = received
    yield client
    client.disconnect()
    client.loop_stop()


def publish(client, kind, payload):
    raw = payload if isinstance(payload, bytes) else json.dumps(payload)
    client.publish(f"garden/{DEVICE}/{kind}", raw, qos=1).wait_for_publish(5)


def telemetry(sequence, **overrides):
    payload = {
        "schema": "bootstrap-telemetry-v0",
        "simulated": True,
        "device_id": DEVICE,
        "sequence": sequence,
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "temperature_c": 28.0,
        "air_humidity_pct": 65.0,
        "soil_moisture_pct": 40.0 + sequence % 50,
    }
    payload.update(overrides)
    return payload


def history(**query):
    params = "&".join(f"{key}={value}" for key, value in query.items())
    status, body = request("GET", f"/devices/{DEVICE}/telemetry?{params}")
    assert status == 200
    return body


def db_connection():
    return psycopg.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "smart_garden"),
        user=os.getenv("DB_USER", "smart_garden"),
        password=os.getenv("DB_PASSWORD", ""),
    )


# --- B-W1-01 ---------------------------------------------------------------


def test_ten_telemetry_messages_are_stored_and_queryable(mqtt_client):
    for sequence in range(1, 11):
        publish(mqtt_client, "telemetry", telemetry(sequence))

    body = wait_for(lambda: (b := history(limit=50))["count"] >= 10 and b)
    assert [item["sequence"] for item in body["items"]] == list(range(1, 11))
    assert {item["device_id"] for item in body["items"]} == {DEVICE}
    assert all(item["simulated"] is True for item in body["items"])

    newest_first = history(limit=3, order="desc")
    assert [item["sequence"] for item in newest_first["items"]] == [10, 9, 8]

    status, latest = request("GET", f"/devices/{DEVICE}/latest")
    assert status == 200
    assert latest["sequence"] == 10 and latest["stale"] is False

    with db_connection() as conn:
        rows = conn.execute(
            "SELECT sequence FROM telemetry WHERE device_id = %s ORDER BY sequence",
            (DEVICE,),
        ).fetchall()
    assert [row[0] for row in rows] == list(range(1, 11))


def test_invalid_messages_are_rejected_and_subscriber_keeps_running(mqtt_client):
    publish(mqtt_client, "telemetry", b"{not json")
    publish(mqtt_client, "telemetry", b"\xff\xfe")
    publish(mqtt_client, "telemetry", {**telemetry(500), "sequence": "oops"})
    publish(mqtt_client, "telemetry", telemetry(501, air_humidity_pct=250))
    publish(mqtt_client, "telemetry", telemetry(502, device_id="someone_else"))
    publish(mqtt_client, "telemetry", telemetry(99))

    wait_for(lambda: request("GET", f"/devices/{DEVICE}/latest")[1].get("sequence") == 99)
    sequences = [item["sequence"] for item in history(limit=100)["items"]]
    assert not {500, 501, 502} & set(sequences)

    with db_connection() as conn:
        reasons = [
            row[0]
            for row in conn.execute(
                "SELECT reason FROM rejected_message WHERE topic = %s ORDER BY id",
                (f"garden/{DEVICE}/telemetry",),
            ).fetchall()
        ]
    assert reasons[:2] == ["invalid_json", "invalid_json"]
    assert "validation_error:sequence" in reasons
    assert "validation_error:air_humidity_pct" in reasons
    assert "device_id_mismatch_topic" in reasons


def test_unknown_device_returns_404():
    assert request("GET", "/devices/nobody_here/latest")[0] == 404
    assert request("GET", "/devices/bad%2Fid/latest")[0] in (404, 422)


# --- B-W1-02 ---------------------------------------------------------------


def next_control(client, command_id):
    while True:
        topic, message = client.received.get(timeout=5)
        if message.get("command_id") == command_id:
            return topic, message


def create(action="pump_on", duration=5):
    body = {"action": action}
    if duration is not None:
        body["duration_seconds"] = duration
    status, command = request("POST", f"/devices/{DEVICE}/commands", body)
    assert status == 202, command
    assert command["status"] == "pending"
    return command


def command_status(command_id):
    status, command = request("GET", f"/commands/{command_id}")
    assert status == 200
    return command


def test_command_applied_only_after_device_ack(mqtt_client):
    command = create()
    command_id = command["command_id"]

    topic, message = next_control(mqtt_client, command_id)
    assert topic == f"garden/{DEVICE}/control"
    assert message["action"] == "pump_on"
    assert message["params"] == {"duration_seconds": 5}
    assert message["expires_at"].endswith("Z")

    # HTTP 202 is not success: still pending until the device answers.
    assert command_status(command_id)["status"] == "pending"

    publish(mqtt_client, "ack", {"command_id": command_id, "device_id": DEVICE, "status": "accepted"})
    accepted = wait_for(
        lambda: (c := command_status(command_id))["device_ack"] == "accepted" and c
    )
    assert accepted["status"] == "pending"

    publish(mqtt_client, "ack", {"command_id": command_id, "device_id": DEVICE, "status": "applied"})
    publish(
        mqtt_client,
        "state",
        {"device_id": DEVICE, "mode": "MANUAL", "relay_state": "on", "last_command_id": command_id},
    )
    applied = wait_for(
        lambda: (c := command_status(command_id))["state_confirmed_at"] and c
    )
    assert applied["status"] == "applied"
    assert applied["device_ack"] == "applied"

    status, state = request("GET", f"/devices/{DEVICE}/state")
    assert status == 200
    assert state["relay_state"] == "on" and state["last_command_id"] == command_id

    listed = request("GET", f"/devices/{DEVICE}/commands")[1]
    assert listed[0]["command_id"] == command_id


def test_command_rejected_keeps_reason(mqtt_client):
    command_id = create(action="pump_off", duration=None)["command_id"]
    next_control(mqtt_client, command_id)
    publish(
        mqtt_client,
        "ack",
        {"command_id": command_id, "device_id": DEVICE, "status": "rejected", "reason": "sensor_error"},
    )
    rejected = wait_for(lambda: (c := command_status(command_id))["status"] != "pending" and c)
    assert rejected["status"] == "rejected"
    assert rejected["reason"] == "sensor_error"


def test_ack_from_other_device_does_not_change_command(mqtt_client):
    command_id = create()["command_id"]
    next_control(mqtt_client, command_id)
    # Topic and payload both claim another device: rejected as a mismatch.
    mqtt_client.publish(
        "garden/intruder_01/ack",
        json.dumps({"command_id": command_id, "device_id": "intruder_01", "status": "applied"}),
        qos=1,
    ).wait_for_publish(5)
    time.sleep(1)
    assert command_status(command_id)["status"] == "pending"


def test_timeout_and_late_ack_never_become_success(mqtt_client):
    command = create()
    command_id = command["command_id"]
    next_control(mqtt_client, command_id)
    expires_at = datetime.fromisoformat(command["expires_at"].replace("Z", "+00:00"))
    wait_seconds = (expires_at - datetime.now(timezone.utc)).total_seconds()

    timed_out = wait_for(
        lambda: (c := command_status(command_id))["status"] != "pending" and c,
        timeout=max(wait_seconds, 0) + 5,
    )
    assert timed_out["status"] == "timeout"
    assert timed_out["late_ack"] is None

    publish(mqtt_client, "ack", {"command_id": command_id, "device_id": DEVICE, "status": "applied"})
    late = wait_for(lambda: (c := command_status(command_id))["late_ack"] and c)
    assert late["status"] == "timeout"
    assert late["late_ack"] == "applied"


def test_invalid_command_requests():
    assert request("POST", f"/devices/{DEVICE}/commands", {"action": "pump_on"})[0] == 422
    assert (
        request("POST", f"/devices/{DEVICE}/commands", {"action": "pump_on", "duration_seconds": 100000})[0]
        == 422
    )
    assert request("POST", f"/devices/{DEVICE}/commands", {"action": "open_valve"})[0] == 422
    assert request("GET", f"/commands/{uuid.uuid4()}")[0] == 404
    assert request("GET", "/commands/not-a-uuid")[0] == 422
