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
    fields = sorted(
        {
            ".".join(str(part) for part in item["loc"]) or "body"
            for item in error.errors()
        }
    )
    return "validation_error:" + ",".join(fields)


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
                    logger.info(
                        "Stored telemetry id=%d device_id=%s sequence=%d simulated=%s",
                        row_id,
                        model.device_id,
                        model.sequence,
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
                    await repository.apply_state(conn, model, data)
                    logger.info(
                        "State device_id=%s relay_state=%s last_command_id=%s",
                        model.device_id,
                        model.relay_state,
                        model.last_command_id,
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
