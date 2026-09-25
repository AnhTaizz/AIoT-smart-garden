"""Validation for MQTT payloads and REST bodies (draft contract for G02)."""

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

DeviceId = Annotated[str, Field(pattern=DEVICE_ID_PATTERN)]
# strict=True rejects numeric strings and booleans; NaN/Infinity are rejected.
Temperature = Annotated[
    float | None, Field(strict=True, ge=-40, le=85, allow_inf_nan=False)
]
Percent = Annotated[float | None, Field(strict=True, ge=0, le=100, allow_inf_nan=False)]
AckStatus = Literal["accepted", "rejected", "applied"]
CommandStatus = Literal["pending", "applied", "rejected", "timeout"]


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


class TelemetryIn(_MqttPayload):
    payload_schema: str = Field(alias="schema", min_length=1, max_length=64)
    simulated: StrictBool
    device_id: DeviceId
    sequence: StrictInt = Field(ge=0)
    measured_at: AwareDatetime
    # Keys are required; null means the sensor reported an error (never 0).
    temperature_c: Temperature
    air_humidity_pct: Percent
    soil_moisture_pct: Percent


class AckIn(_MqttPayload):
    command_id: UUID
    device_id: DeviceId
    status: AckStatus
    reason: str | None = Field(default=None, max_length=200)
    acked_at: AwareDatetime | None = None


class StateIn(_MqttPayload):
    device_id: DeviceId
    mode: str | None = Field(default=None, max_length=32)
    relay_state: str | None = Field(default=None, max_length=32)
    last_command_id: UUID | None = None
    reported_at: AwareDatetime | None = None


class CommandCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["pump_on", "pump_off"]
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
    sequence: int
    measured_at: datetime
    received_at: datetime
    temperature_c: float | None
    air_humidity_pct: float | None
    soil_moisture_pct: float | None
    simulated: bool
    payload_schema: str


class LatestTelemetryOut(TelemetryOut):
    stale: bool
    stale_after_seconds: int


class CommandOut(BaseModel):
    command_id: UUID
    device_id: str
    action: str
    params: dict[str, Any]
    status: CommandStatus
    device_ack: AckStatus | None
    reason: str | None
    created_at: datetime
    expires_at: datetime
    published_at: datetime | None
    acked_at: datetime | None
    finalized_at: datetime | None
    state_confirmed_at: datetime | None
    late_ack: AckStatus | None
    late_ack_at: datetime | None


class DeviceStateOut(BaseModel):
    device_id: str
    mode: str | None
    relay_state: str | None
    last_command_id: UUID | None
    reported_at: datetime | None
    received_at: datetime
