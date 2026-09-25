"""Validation for MQTT payloads and REST bodies.

Implements the v1 contract proposal in docs/INTERFACES.md, which is still
DRAFT: the team confirms it at G02.
"""

import json
import re
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    model_validator,
)

DEVICE_ID_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"
TOPIC_PREFIX = "garden"
MQTT_KINDS = ("telemetry", "ack", "state")
TELEMETRY_SCHEMA = "telemetry-v1"
COMMAND_SCHEMA = "command-v1"
ACK_SCHEMA = "ack-v1"
STATE_SCHEMA = "state-v1"

DeviceId = Annotated[str, Field(pattern=DEVICE_ID_PATTERN)]
BootId = Annotated[str, Field(pattern=DEVICE_ID_PATTERN)]
# strict=True rejects numeric strings and booleans; NaN/Infinity are rejected.
Temperature = Annotated[
    float | None, Field(strict=True, ge=-40, le=85, allow_inf_nan=False)
]
Percent = Annotated[float | None, Field(strict=True, ge=0, le=100, allow_inf_nan=False)]
SensorHealth = Literal["ok", "error"]
RelayState = Literal["on", "off"]
DeviceMode = Literal["MANUAL", "AUTO"]
AckStatus = Literal["accepted", "rejected", "applied"]
CommandStatus = Literal["pending", "applied", "rejected", "timeout"]
CommandAction = Literal["pump_on", "pump_off"]
DeviceRejectReason = Literal[
    "invalid_payload",
    "unsupported_action",
    "invalid_duration",
    "boot_mismatch",
    "clock_unsynced",
    "expired",
    "superseded",
    "busy",
    "safety_lock",
    "relay_error",
    "sensor_error",
    "internal_error",
]

# The relay state that proves a command was carried out.
EXPECTED_RELAY_STATE: dict[str, str] = {"pump_on": "on", "pump_off": "off"}


class PayloadError(ValueError):
    """An MQTT payload that must not be stored as valid data."""


def parse_topic(topic: str) -> tuple[str, str]:
    """Return (device_id, kind) for garden/<device_id>/<kind> topics."""
    parts = topic.split("/")
    if len(parts) != 3 or parts[0] != TOPIC_PREFIX or parts[2] not in MQTT_KINDS:
        raise PayloadError("unsupported_topic")
    device_id = parts[1]
    if not re.fullmatch(DEVICE_ID_PATTERN, device_id):
        raise PayloadError("invalid_topic_device_id")
    return device_id, parts[2]


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite number {value}")


def decode_json_object(payload: bytes) -> dict[str, Any]:
    try:
        text = payload.decode("utf-8")
        data = json.loads(text, parse_constant=_reject_constant)
    except (UnicodeDecodeError, ValueError) as error:
        raise PayloadError("invalid_json") from error
    if not isinstance(data, dict):
        raise PayloadError("json_not_object")
    return data


class _MqttPayload(BaseModel):
    # Unknown fields are kept in the raw JSON column, not rejected.
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class SensorStatus(BaseModel):
    """Per-sensor health. Extra sensors may be added without breaking this."""

    model_config = ConfigDict(extra="allow")

    aht20: SensorHealth
    soil: SensorHealth


class TelemetryIn(_MqttPayload):
    payload_schema: Literal["telemetry-v1"] = Field(alias="schema")
    simulated: StrictBool
    device_id: DeviceId
    boot_id: BootId
    sequence: StrictInt = Field(ge=1)
    clock_synced: StrictBool
    # Null when the device has no trustworthy UTC clock; never a made-up time.
    measured_at: AwareDatetime | None
    uptime_ms: StrictInt = Field(ge=0)
    # Keys are required; null means the sensor reported an error (never 0).
    temperature_c: Temperature
    air_humidity_pct: Percent
    soil_moisture_pct: Percent
    sensor_status: SensorStatus

    @model_validator(mode="after")
    def _check_consistency(self) -> "TelemetryIn":
        if self.clock_synced and self.measured_at is None:
            raise ValueError("measured_at is required when clock_synced is true")
        if not self.clock_synced and self.measured_at is not None:
            raise ValueError("measured_at must be null when clock_synced is false")

        # A reading is either present with status "ok", or null with status
        # "error". One null reading next to status "ok" is contradictory.
        aht20_readings = (self.temperature_c, self.air_humidity_pct)
        if self.sensor_status.aht20 == "error":
            if any(reading is not None for reading in aht20_readings):
                raise ValueError(
                    "temperature_c and air_humidity_pct must be null when"
                    " sensor_status.aht20 is 'error'"
                )
        elif any(reading is None for reading in aht20_readings):
            raise ValueError(
                "sensor_status.aht20 must be 'error' when temperature_c or"
                " air_humidity_pct is null"
            )

        if self.sensor_status.soil == "error":
            if self.soil_moisture_pct is not None:
                raise ValueError(
                    "soil_moisture_pct must be null when sensor_status.soil is"
                    " 'error'"
                )
        elif self.soil_moisture_pct is None:
            raise ValueError(
                "sensor_status.soil must be 'error' when soil_moisture_pct is null"
            )
        return self


class AckIn(_MqttPayload):
    payload_schema: Literal["ack-v1"] = Field(alias="schema")
    command_id: UUID
    device_id: DeviceId
    boot_id: BootId
    status: AckStatus
    reason: DeviceRejectReason | None
    clock_synced: StrictBool
    acked_at: AwareDatetime | None

    @model_validator(mode="after")
    def _check_consistency(self) -> "AckIn":
        if self.clock_synced != (self.acked_at is not None):
            raise ValueError(
                "acked_at must be present exactly when clock_synced is true"
            )
        if self.status == "rejected" and self.reason is None:
            raise ValueError("reason is required when status is rejected")
        if self.status != "rejected" and self.reason is not None:
            raise ValueError("reason must be null unless status is rejected")
        return self


class StateIn(_MqttPayload):
    payload_schema: Literal["state-v1"] = Field(alias="schema")
    device_id: DeviceId
    boot_id: BootId
    state_sequence: StrictInt = Field(ge=1)
    mode: DeviceMode
    relay_state: RelayState
    last_command_id: UUID | None
    last_command_sequence: StrictInt | None = Field(default=None, ge=1)
    clock_synced: StrictBool
    reported_at: AwareDatetime | None
    uptime_ms: StrictInt = Field(ge=0)

    @model_validator(mode="after")
    def _check_consistency(self) -> "StateIn":
        if self.clock_synced != (self.reported_at is not None):
            raise ValueError(
                "reported_at must be present exactly when clock_synced is true"
            )
        if (self.last_command_id is None) != (self.last_command_sequence is None):
            raise ValueError(
                "last_command_id and last_command_sequence must both be null or present"
            )
        return self


class CommandCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: CommandAction
    duration_seconds: StrictInt | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _check_duration(self) -> "CommandCreate":
        if self.action == "pump_on" and self.duration_seconds is None:
            raise ValueError("pump_on requires duration_seconds")
        if self.action == "pump_off" and self.duration_seconds is not None:
            raise ValueError("pump_off does not accept duration_seconds")
        return self


class TelemetryOut(BaseModel):
    id: int
    device_id: str
    boot_id: str
    sequence: int
    clock_synced: bool
    measured_at: datetime | None
    received_at: datetime
    uptime_ms: int
    temperature_c: float | None
    air_humidity_pct: float | None
    soil_moisture_pct: float | None
    sensor_status: dict[str, Any]
    simulated: bool
    payload_schema: str


class LatestTelemetryOut(TelemetryOut):
    stale: bool
    stale_after_seconds: int


class TelemetryPage(BaseModel):
    device_id: str
    count: int
    order: Literal["asc", "desc"]
    items: list[TelemetryOut]


class CommandOut(BaseModel):
    command_id: UUID
    device_id: str
    command_sequence: int
    action: str
    params: dict[str, Any]
    target_boot_id: str | None
    status: CommandStatus
    device_ack: AckStatus | None
    reason: str | None
    created_at: datetime
    expires_at: datetime
    published_at: datetime | None
    acked_at: datetime | None
    ack_boot_id: str | None
    state_confirmed_at: datetime | None
    confirmed_relay_state: RelayState | None
    confirmed_state_sequence: int | None
    confirmed_boot_id: str | None
    finalized_at: datetime | None
    late_ack: AckStatus | None
    late_ack_at: datetime | None


class CommandList(BaseModel):
    device_id: str
    count: int
    items: list[CommandOut]


class DeviceStateOut(BaseModel):
    device_id: str
    boot_id: str
    state_sequence: int
    mode: DeviceMode
    relay_state: RelayState
    last_command_id: UUID | None
    last_command_sequence: int | None
    clock_synced: bool
    reported_at: datetime | None
    received_at: datetime
    stale: bool
    stale_after_seconds: int
