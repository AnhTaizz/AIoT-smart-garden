"""Device-side logic of the G02 v1 contract, without any MQTT or I/O.

Keeping the decisions in pure functions lets the unit tests cover the rules that
matter for pump safety: duplicates, target boot, expiry, ordering after a STOP
and busy. Thanh (A) owns the firmware; this module is the minimal reference
implementation used to test the contract end to end with the backend.
"""

from __future__ import annotations

import random
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

TELEMETRY_SCHEMA = "telemetry-v1"
ACK_SCHEMA = "ack-v1"
STATE_SCHEMA = "state-v1"
COMMAND_SCHEMA = "command-v1"
ACTIONS = ("pump_on", "pump_off")
DEFAULT_PUMP_MAX_SECONDS = 60
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def new_boot_id() -> str:
    return f"boot_{uuid.uuid4().hex[:8]}"


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo is not None else None


def is_identifier(value: Any) -> bool:
    return isinstance(value, str) and IDENTIFIER_PATTERN.fullmatch(value) is not None


def is_uuid(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


@dataclass(frozen=True)
class Decision:
    """What the device does with one command.

    status None means the command is not for this device and gets no ACK.
    """

    status: str | None
    reason: str | None = None
    duplicate: bool = False


@dataclass
class DeviceRuntime:
    """In-RAM state of one simulated device for the current boot."""

    device_id: str
    boot_id: str = field(default_factory=new_boot_id)
    clock_synced: bool = True
    pump_max_seconds: int = DEFAULT_PUMP_MAX_SECONDS
    relay_state: str = "off"
    # Ordering mark: only ever moves forward, so an ON issued before a STOP can
    # never start after that STOP was applied.
    order_mark: int = 0
    state_sequence: int = 0
    telemetry_sequence: int = 0
    running_command_id: str | None = None
    pump_stop_at: float | None = None
    last_command_id: str | None = None
    last_command_sequence: int | None = None
    outcomes: dict[str, Decision] = field(default_factory=dict)
    uptime_ms: int = 0

    # --- command handling --------------------------------------------------

    def handle_command(
        self, payload: Any, now: datetime | None = None, monotonic: float = 0.0
    ) -> Decision:
        """Apply the contract's check order and return the ACK to publish."""
        if not isinstance(payload, dict):
            return Decision(None)
        command_id = payload.get("command_id")
        if not is_uuid(command_id):
            return Decision(None)
        payload_device_id = payload.get("device_id")
        if not is_identifier(payload_device_id):
            return self._reject(command_id, "invalid_payload")
        if payload_device_id != self.device_id:
            return Decision(None)

        # 3. A repeat of a command already answered in this boot never runs
        #    again and never extends the pump timer.
        if command_id in self.outcomes:
            previous = self.outcomes[command_id]
            return Decision(previous.status, previous.reason, duplicate=True)

        # Validate the common envelope before applying action-specific safety
        # rules. OFF may ignore a deadline, but it must still be a well-formed
        # command from this contract.
        if payload.get("schema") != COMMAND_SCHEMA:
            return self._reject(command_id, "invalid_payload")

        sequence = payload.get("command_sequence")
        params = payload.get("params")
        target_boot_id = payload.get("target_boot_id")
        issued_at = parse_iso(payload.get("issued_at"))
        expires_at = parse_iso(payload.get("expires_at"))
        if (
            not isinstance(sequence, int)
            or isinstance(sequence, bool)
            or sequence < 1
            or not isinstance(params, dict)
            or not (
                target_boot_id is None or is_identifier(target_boot_id)
            )
            or issued_at is None
            or expires_at is None
        ):
            return self._reject(command_id, "invalid_payload")

        action = payload.get("action")
        if action not in ACTIONS:
            return self._reject(command_id, "unsupported_action")

        if action == "pump_off":
            if params:
                return self._reject(command_id, "invalid_payload")
            # STOP is exempt from boot, clock, expiry, ordering and busy checks:
            # turning the pump off is always the safer outcome.
            return self._apply_off(command_id, sequence)

        if set(params) != {"duration_seconds"}:
            return self._reject(command_id, "invalid_payload")
        duration = params.get("duration_seconds")
        if (
            not isinstance(duration, int)
            or isinstance(duration, bool)
            or duration < 1
            or duration > self.pump_max_seconds
        ):
            return self._reject(command_id, "invalid_duration")

        if payload.get("target_boot_id") != self.boot_id:
            return self._reject(command_id, "boot_mismatch")

        if not self.clock_synced or now is None:
            # Without a trustworthy clock the device cannot tell whether the
            # deadline has passed, so it refuses to start the pump.
            return self._reject(command_id, "clock_unsynced")

        if expires_at <= now:
            return self._reject(command_id, "expired")

        if sequence <= self.order_mark:
            return self._reject(command_id, "superseded")

        if self.running_command_id is not None:
            return self._reject(command_id, "busy")

        return self._apply_on(command_id, sequence, duration, monotonic)

    def _reject(self, command_id: str, reason: str) -> Decision:
        decision = Decision("rejected", reason)
        self.outcomes[command_id] = decision
        return decision

    def _apply_on(
        self, command_id: str, sequence: int, duration: int, monotonic: float
    ) -> Decision:
        self.relay_state = "on"
        self.running_command_id = command_id
        self.pump_stop_at = monotonic + duration
        self._mark_applied(command_id, sequence)
        decision = Decision("applied")
        self.outcomes[command_id] = decision
        return decision

    def _apply_off(self, command_id: str, sequence: int) -> Decision:
        self.relay_state = "off"
        self.running_command_id = None
        self.pump_stop_at = None
        self._mark_applied(command_id, sequence)
        decision = Decision("applied")
        self.outcomes[command_id] = decision
        return decision

    def _mark_applied(self, command_id: str, sequence: int) -> None:
        # max(): a repeated or older STOP must not drag the mark backwards.
        self.order_mark = max(self.order_mark, sequence)
        self.last_command_id = command_id
        self.last_command_sequence = sequence

    def pump_finished(self, monotonic: float) -> bool:
        """True once a running pump has reached its duration."""
        if self.pump_stop_at is None:
            return False
        if monotonic < self.pump_stop_at:
            return False
        self.relay_state = "off"
        self.running_command_id = None
        self.pump_stop_at = None
        return True

    def reboot(self) -> None:
        self.boot_id = new_boot_id()
        self.relay_state = "off"
        self.order_mark = 0
        self.state_sequence = 0
        self.telemetry_sequence = 0
        self.running_command_id = None
        self.pump_stop_at = None
        self.last_command_id = None
        self.last_command_sequence = None
        self.outcomes.clear()

    # --- payload builders --------------------------------------------------

    def telemetry_payload(
        self,
        random_source: random.Random,
        aht20_ok: bool = True,
        soil_ok: bool = True,
    ) -> dict[str, Any]:
        self.telemetry_sequence += 1
        return {
            "schema": TELEMETRY_SCHEMA,
            "simulated": True,
            "device_id": self.device_id,
            "boot_id": self.boot_id,
            "sequence": self.telemetry_sequence,
            "clock_synced": self.clock_synced,
            "measured_at": utc_now_iso() if self.clock_synced else None,
            "uptime_ms": self.uptime_ms,
            "temperature_c": round(random_source.uniform(24.0, 32.0), 2)
            if aht20_ok
            else None,
            "air_humidity_pct": round(random_source.uniform(55.0, 85.0), 2)
            if aht20_ok
            else None,
            "soil_moisture_pct": round(random_source.uniform(30.0, 70.0), 2)
            if soil_ok
            else None,
            "sensor_status": {
                "aht20": "ok" if aht20_ok else "error",
                "soil": "ok" if soil_ok else "error",
            },
        }

    def ack_payload(self, command_id: str, decision: Decision) -> dict[str, Any]:
        return {
            "schema": ACK_SCHEMA,
            "command_id": command_id,
            "device_id": self.device_id,
            "boot_id": self.boot_id,
            "status": decision.status,
            "reason": decision.reason,
            "clock_synced": self.clock_synced,
            "acked_at": utc_now_iso() if self.clock_synced else None,
        }

    def state_payload(self) -> dict[str, Any]:
        self.state_sequence += 1
        return {
            "schema": STATE_SCHEMA,
            "device_id": self.device_id,
            "boot_id": self.boot_id,
            "state_sequence": self.state_sequence,
            "mode": "MANUAL",
            "relay_state": self.relay_state,
            "last_command_id": self.last_command_id,
            "last_command_sequence": self.last_command_sequence,
            "clock_synced": self.clock_synced,
            "reported_at": utc_now_iso() if self.clock_synced else None,
            "uptime_ms": self.uptime_ms,
        }
