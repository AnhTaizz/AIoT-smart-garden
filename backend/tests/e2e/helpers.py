"""Shared helpers for e2e tests against a running stack.

Every test run uses a fresh device_id, so e2e traffic never mixes with the
demo device `node_01`.
"""

import json
import os
import queue
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone

import psycopg
from paho.mqtt import client as mqtt

API = os.getenv("E2E_API_BASE_URL", "").rstrip("/")
MQTT_HOST = os.getenv("E2E_MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("E2E_MQTT_PORT", "1883"))
TELEMETRY_SCHEMA = "telemetry-v1"


def new_device_id() -> str:
    return f"e2e_{uuid.uuid4().hex[:8]}"


def new_boot_id() -> str:
    return f"boot_{uuid.uuid4().hex[:8]}"


def request(method, path, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        API + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status, json.loads(response.read() or b"null")
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"null")


def wait_for(predicate, timeout=10.0, interval=0.2, message="condition not met"):
    deadline = time.monotonic() + timeout
    while True:
        value = predicate()
        if value:
            return value
        if time.monotonic() > deadline:
            raise AssertionError(f"{message} (timeout {timeout}s)")
        time.sleep(interval)


def error_code(body):
    """Read the machine-readable code from a standard error body."""
    detail = body.get("detail") if isinstance(body, dict) else None
    if isinstance(detail, dict):
        return detail.get("code")
    return detail


def db_connection():
    return psycopg.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "smart_garden"),
        user=os.getenv("DB_USER", "smart_garden"),
        password=os.getenv("DB_PASSWORD", ""),
    )


def iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


class FakeDevice:
    """An MQTT client that speaks the device side of the G02 contract."""

    def __init__(self, device_id=None, boot_id=None, auto_respond=False):
        self.device_id = device_id or new_device_id()
        self.boot_id = boot_id or new_boot_id()
        # auto_respond mimics a real device: it answers from the MQTT callback,
        # often before the POST that created the command has returned.
        self.auto_respond = auto_respond
        self.state_sequence = 0
        self.telemetry_sequence = 0
        self.control = queue.Queue()
        self._connected = queue.Queue()
        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"{self.device_id}-test",
            clean_session=True,
        )
        self._client.on_connect = lambda c, u, f, rc, p: self._connected.put(rc)
        self._client.on_message = lambda c, u, m: self._on_control(
            json.loads(m.payload)
        )

    def _on_control(self, message):
        self.control.put(message)
        if not self.auto_respond:
            return
        relay = "on" if message.get("action") == "pump_on" else "off"
        self.publish_ack(message["command_id"], "applied")
        self.publish_state(
            relay_state=relay,
            last_command_id=message["command_id"],
            last_command_sequence=message.get("command_sequence"),
        )

    def __enter__(self):
        self._client.connect(MQTT_HOST, MQTT_PORT)
        self._client.loop_start()
        assert self._connected.get(timeout=5) == 0
        self._client.subscribe(f"garden/{self.device_id}/control", qos=1)
        return self

    def __exit__(self, *_exc):
        self._client.disconnect()
        self._client.loop_stop()

    # --- publishing --------------------------------------------------------

    def _publish(self, kind, payload):
        raw = payload if isinstance(payload, bytes) else json.dumps(payload)
        self._client.publish(f"garden/{self.device_id}/{kind}", raw, qos=1).wait_for_publish(5)

    def telemetry_payload(self, sequence=None, **overrides):
        if sequence is None:
            self.telemetry_sequence += 1
            sequence = self.telemetry_sequence
        payload = {
            "schema": TELEMETRY_SCHEMA,
            "simulated": True,
            "device_id": self.device_id,
            "boot_id": self.boot_id,
            "sequence": sequence,
            "clock_synced": True,
            "measured_at": iso(datetime.now(timezone.utc)),
            "uptime_ms": 1000 * sequence,
            "temperature_c": 28.0,
            "air_humidity_pct": 65.0,
            "soil_moisture_pct": 41.0,
            "sensor_status": {"aht20": "ok", "soil": "ok"},
        }
        payload.update(overrides)
        return payload

    def publish_telemetry(self, sequence=None, **overrides):
        payload = (
            overrides.pop("raw")
            if "raw" in overrides
            else self.telemetry_payload(sequence, **overrides)
        )
        self._publish("telemetry", payload)
        return payload

    def publish_ack(self, command_id, status, boot_id=None, reason=None, **overrides):
        payload = {
            "schema": "ack-v1",
            "command_id": command_id,
            "device_id": self.device_id,
            "boot_id": boot_id or self.boot_id,
            "status": status,
            "reason": reason,
            "clock_synced": True,
            "acked_at": iso(datetime.now(timezone.utc)),
        }
        payload.update(overrides)
        self._publish("ack", payload)
        return payload

    def publish_state(
        self,
        relay_state="off",
        last_command_id=None,
        last_command_sequence=None,
        boot_id=None,
        state_sequence=None,
        mode="MANUAL",
        **overrides,
    ):
        if last_command_id is not None and last_command_sequence is None:
            # Keep every synthetic state valid under state-v1. Tests that need
            # a deliberately malformed pair can still pass it via overrides.
            last_command_sequence = self.command(last_command_id)["command_sequence"]
        if state_sequence is None:
            self.state_sequence += 1
            state_sequence = self.state_sequence
        payload = {
            "schema": "state-v1",
            "device_id": self.device_id,
            "boot_id": boot_id or self.boot_id,
            "state_sequence": state_sequence,
            "mode": mode,
            "relay_state": relay_state,
            "last_command_id": last_command_id,
            "last_command_sequence": last_command_sequence,
            "clock_synced": True,
            "reported_at": iso(datetime.now(timezone.utc)),
            "uptime_ms": 1000 * state_sequence,
        }
        payload.update(overrides)
        self._publish("state", payload)
        return payload

    def announce(self, relay_state="off"):
        """Publish the state a device sends right after connecting."""
        payload = self.publish_state(relay_state=relay_state)
        wait_for(
            lambda: request("GET", f"/devices/{self.device_id}/state")[1].get("boot_id")
            == self.boot_id,
            message="backend did not register the device boot",
        )
        return payload

    def reboot(self, boot_id=None):
        self.boot_id = boot_id or new_boot_id()
        self.state_sequence = 0
        self.telemetry_sequence = 0
        return self.boot_id

    # --- helpers -----------------------------------------------------------

    def next_control(self, command_id, timeout=5):
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AssertionError("control message not received")
            message = self.control.get(timeout=remaining)
            if message.get("command_id") == command_id:
                return message

    def create_command(self, action="pump_on", duration=5, expect=202):
        body = {"action": action}
        if duration is not None:
            body["duration_seconds"] = duration
        status, command = request("POST", f"/devices/{self.device_id}/commands", body)
        assert status == expect, (status, command)
        return command

    def command(self, command_id):
        status, body = request("GET", f"/commands/{command_id}")
        assert status == 200, (status, body)
        return body

    def state(self):
        status, body = request("GET", f"/devices/{self.device_id}/state")
        assert status == 200, (status, body)
        return body

    def history(self, **query):
        params = "&".join(f"{key}={value}" for key, value in query.items())
        status, body = request("GET", f"/devices/{self.device_id}/telemetry?{params}")
        assert status == 200, (status, body)
        return body

    def latest(self):
        return request("GET", f"/devices/{self.device_id}/latest")

    def wait_for_count(self, count, timeout=10.0, **query):
        query.setdefault("limit", 50)
        return wait_for(
            lambda: (body := self.history(**query))["count"] == count and body,
            timeout=timeout,
            message=f"history did not reach {count} rows",
        )

    def wait_for_ack(self, command_id, ack_status, timeout=10.0):
        return wait_for(
            lambda: (c := self.command(command_id))["device_ack"] == ack_status and c,
            timeout=timeout,
            message=f"device_ack did not become {ack_status}",
        )

    def wait_status(self, command_id, *statuses, timeout=25.0):
        return wait_for(
            lambda: (c := self.command(command_id))["status"] in statuses and c,
            timeout=timeout,
            message=f"command did not reach {statuses}",
        )


def expires_in(command) -> float:
    expires_at = datetime.fromisoformat(command["expires_at"].replace("Z", "+00:00"))
    return (expires_at - datetime.now(timezone.utc)).total_seconds()


def past_iso(seconds=60) -> str:
    return iso(datetime.now(timezone.utc) - timedelta(seconds=seconds))
