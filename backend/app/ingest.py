"""Consume MQTT messages: validate, store valid data, record rejects."""

import asyncio
import logging

from psycopg_pool import AsyncConnectionPool
from pydantic import ValidationError

from . import repository
from .schemas import (
    AckIn,
    PayloadError,
    StateIn,
    TelemetryIn,
    decode_json_object,
    parse_topic,
)

logger = logging.getLogger(__name__)

MODELS = {"telemetry": TelemetryIn, "ack": AckIn, "state": StateIn}


def summarize_validation_error(error: ValidationError) -> str:
    """Name the offending fields, or the rule for whole-payload checks."""
    parts = set()
    for item in error.errors():
        field = ".".join(str(part) for part in item["loc"])
        if field:
            parts.add(field)
            continue
        # Cross-field rules (clock vs measured_at, sensor_status vs readings)
        # have no field location, so keep their message instead of "body".
        message = str(item.get("msg", "invalid payload"))
        parts.add(message.removeprefix("Value error, ")[:120])
    return "validation_error:" + ",".join(sorted(parts))


def validate_message(topic: str, payload: bytes) -> tuple[str, object, dict]:
    """Return (kind, model, raw dict) or raise PayloadError / ValidationError."""
    topic_device_id, kind = parse_topic(topic)
    data = decode_json_object(payload)
    model = MODELS[kind].model_validate(data)
    if model.device_id != topic_device_id:
        raise PayloadError("device_id_mismatch_topic")
    return kind, model, data


class MessageHandler:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def handle(self, topic: str, payload: bytes) -> None:
        try:
            kind, model, data = validate_message(topic, payload)
            async with self._pool.connection() as conn:
                if kind == "telemetry":
                    row_id = await repository.insert_telemetry(conn, topic, model, data)
                    if row_id is None:
                        # Same device_id + boot_id + sequence: a resend, not an
                        # invalid payload, so it is dropped without a reject row.
                        logger.info(
                            "Ignored duplicate telemetry device_id=%s boot_id=%s"
                            " sequence=%d",
                            model.device_id,
                            model.boot_id,
                            model.sequence,
                        )
                    else:
                        logger.info(
                            "Stored telemetry id=%d device_id=%s boot_id=%s"
                            " sequence=%d clock_synced=%s simulated=%s",
                            row_id,
                            model.device_id,
                            model.boot_id,
                            model.sequence,
                            model.clock_synced,
                            model.simulated,
                        )
                elif kind == "ack":
                    outcome = await repository.apply_ack(conn, model, data)
                    logger.info(
                        "ACK command_id=%s status=%s -> %s",
                        model.command_id,
                        model.status,
                        outcome,
                    )
                else:
                    outcome = await repository.apply_state(conn, model, data)
                    logger.info(
                        "State device_id=%s boot_id=%s state_sequence=%d"
                        " relay_state=%s last_command_id=%s -> %s",
                        model.device_id,
                        model.boot_id,
                        model.state_sequence,
                        model.relay_state,
                        model.last_command_id,
                        outcome,
                    )
        except PayloadError as error:
            await self._reject(topic, str(error), payload)
        except ValidationError as error:
            await self._reject(topic, summarize_validation_error(error), payload)

    async def _reject(self, topic: str, reason: str, payload: bytes) -> None:
        logger.warning("Rejected MQTT message topic=%s reason=%s", topic, reason)
        async with self._pool.connection() as conn:
            await repository.insert_rejected(conn, topic, reason, payload)


async def consume(
    queue: "asyncio.Queue[tuple[str, bytes]]", handler: MessageHandler
) -> None:
    """Process messages forever; one bad message never stops the loop."""
    while True:
        topic, payload = await queue.get()
        try:
            await handler.handle(topic, payload)
        except Exception:
            logger.exception("Failed to process MQTT message topic=%s", topic)
        finally:
            queue.task_done()
