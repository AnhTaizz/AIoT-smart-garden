"""SQL for telemetry, rejected messages and the command lifecycle."""

from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg import AsyncConnection
from psycopg.types.json import Jsonb

from .schemas import AckIn, PayloadError, StateIn, TelemetryIn

RAW_PAYLOAD_LIMIT = 4096
COMMAND_COLUMNS = (
    "command_id, device_id, action, params, status, device_ack, reason,"
    " created_at, expires_at, published_at, acked_at, finalized_at,"
    " state_confirmed_at, late_ack, late_ack_at"
)
TELEMETRY_COLUMNS = (
    "id, device_id, sequence, measured_at, received_at, temperature_c,"
    " air_humidity_pct, soil_moisture_pct, simulated, payload_schema"
)


# --- telemetry -------------------------------------------------------------


async def insert_telemetry(
    conn: AsyncConnection, topic: str, telemetry: TelemetryIn, raw: dict[str, Any]
) -> int:
    cursor = await conn.execute(
        "INSERT INTO telemetry (device_id, sequence, measured_at, temperature_c,"
        " air_humidity_pct, soil_moisture_pct, simulated, payload_schema, topic,"
        " raw_payload)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
        (
            telemetry.device_id,
            telemetry.sequence,
            telemetry.measured_at,
            telemetry.temperature_c,
            telemetry.air_humidity_pct,
            telemetry.soil_moisture_pct,
            telemetry.simulated,
            telemetry.payload_schema,
            topic,
            Jsonb(raw),
        ),
    )
    row = await cursor.fetchone()
    return row["id"]


async def insert_rejected(
    conn: AsyncConnection, topic: str, reason: str, payload: bytes
) -> None:
    # PostgreSQL TEXT cannot hold NUL, so keep a lossy but safe copy for debugging.
    text = payload.decode("utf-8", "replace").replace("\x00", "�")
    await conn.execute(
        "INSERT INTO rejected_message (topic, reason, raw_payload)"
        " VALUES (%s, %s, %s)",
        (topic, reason[:500], text[:RAW_PAYLOAD_LIMIT]),
    )


async def latest_telemetry(
    conn: AsyncConnection, device_id: str, stale_seconds: int
) -> dict[str, Any] | None:
    cursor = await conn.execute(
        f"SELECT {TELEMETRY_COLUMNS},"
        " now() - received_at > make_interval(secs => %s) AS stale"
        " FROM telemetry WHERE device_id = %s"
        " ORDER BY received_at DESC, id DESC LIMIT 1",
        (stale_seconds, device_id),
    )
    return await cursor.fetchone()


async def telemetry_history(
    conn: AsyncConnection,
    device_id: str,
    since: datetime | None,
    until: datetime | None,
    limit: int,
) -> list[dict[str, Any]]:
    """Most recent `limit` rows with measured_at in [since, until], newest first."""
    cursor = await conn.execute(
        f"SELECT {TELEMETRY_COLUMNS} FROM telemetry"
        " WHERE device_id = %s"
        " AND (%s::timestamptz IS NULL OR measured_at >= %s)"
        " AND (%s::timestamptz IS NULL OR measured_at <= %s)"
        " ORDER BY measured_at DESC, id DESC LIMIT %s",
        (device_id, since, since, until, until, limit),
    )
    return await cursor.fetchall()


# --- commands --------------------------------------------------------------


async def insert_command(
    conn: AsyncConnection,
    command_id: UUID,
    device_id: str,
    action: str,
    params: dict[str, Any],
    timeout_seconds: int,
) -> dict[str, Any]:
    cursor = await conn.execute(
        "INSERT INTO command (command_id, device_id, action, params, status,"
        " expires_at)"
        " VALUES (%s, %s, %s, %s, 'pending', now() + make_interval(secs => %s))"
        f" RETURNING {COMMAND_COLUMNS}",
        (command_id, device_id, action, Jsonb(params), timeout_seconds),
    )
    return await cursor.fetchone()


async def mark_published(conn: AsyncConnection, command_id: UUID) -> dict[str, Any]:
    cursor = await conn.execute(
        "UPDATE command SET published_at = now() WHERE command_id = %s"
        f" RETURNING {COMMAND_COLUMNS}",
        (command_id,),
    )
    return await cursor.fetchone()


async def mark_publish_failed(
    conn: AsyncConnection, command_id: UUID
) -> dict[str, Any] | None:
    cursor = await conn.execute(
        "UPDATE command SET status = 'rejected', reason = 'backend_publish_failed',"
        " finalized_at = now() WHERE command_id = %s AND status = 'pending'"
        f" RETURNING {COMMAND_COLUMNS}",
        (command_id,),
    )
    return await cursor.fetchone()


async def expire_commands(
    conn: AsyncConnection, command_id: UUID | None = None
) -> list[UUID]:
    """Move pending commands past their deadline to `timeout`."""
    cursor = await conn.execute(
        "UPDATE command SET status = 'timeout', finalized_at = expires_at"
        " WHERE status = 'pending' AND expires_at < now()"
        " AND (%s::uuid IS NULL OR command_id = %s)"
        " RETURNING command_id",
        (command_id, command_id),
    )
    return [row["command_id"] for row in await cursor.fetchall()]


async def get_command(
    conn: AsyncConnection, command_id: UUID
) -> dict[str, Any] | None:
    cursor = await conn.execute(
        f"SELECT {COMMAND_COLUMNS} FROM command WHERE command_id = %s",
        (command_id,),
    )
    return await cursor.fetchone()


async def list_commands(
    conn: AsyncConnection, device_id: str, limit: int
) -> list[dict[str, Any]]:
    cursor = await conn.execute(
        f"SELECT {COMMAND_COLUMNS} FROM command WHERE device_id = %s"
        " ORDER BY created_at DESC LIMIT %s",
        (device_id, limit),
    )
    return await cursor.fetchall()


async def apply_ack(conn: AsyncConnection, ack: AckIn, raw: dict[str, Any]) -> str:
    """Advance a command from a device ACK and return the outcome for logs.

    Only an ACK for a still-pending, unexpired command can change `status`.
    An ACK after the deadline is stored as `late_ack` and never turns a
    `timeout` into success.
    """
    async with conn.transaction():
        cursor = await conn.execute(
            "SELECT device_id, status, expires_at < now() AS expired"
            " FROM command WHERE command_id = %s FOR UPDATE",
            (ack.command_id,),
        )
        command = await cursor.fetchone()
        late = False
        if command is None:
            outcome = "unknown_command"
        elif command["device_id"] != ack.device_id:
            raise PayloadError("ack_device_mismatch")
        else:
            status = command["status"]
            if status == "pending" and command["expired"]:
                await conn.execute(
                    "UPDATE command SET status = 'timeout', finalized_at = expires_at"
                    " WHERE command_id = %s",
                    (ack.command_id,),
                )
                status = "timeout"
            if status == "timeout":
                late = True
                await conn.execute(
                    "UPDATE command SET late_ack = %s, late_ack_at = now()"
                    " WHERE command_id = %s",
                    (ack.status, ack.command_id),
                )
                outcome = "late_ack"
            elif status != "pending":
                outcome = "ignored_final"
            elif ack.status == "accepted":
                await conn.execute(
                    "UPDATE command SET device_ack = 'accepted', acked_at = now()"
                    " WHERE command_id = %s",
                    (ack.command_id,),
                )
                outcome = "accepted"
            else:
                await conn.execute(
                    "UPDATE command SET status = %s, device_ack = %s, reason = %s,"
                    " acked_at = now(), finalized_at = now() WHERE command_id = %s",
                    (ack.status, ack.status, ack.reason, ack.command_id),
                )
                outcome = ack.status
        await conn.execute(
            "INSERT INTO command_event (command_id, device_id, kind, ack_status,"
            " late, payload) VALUES (%s, %s, 'ack', %s, %s, %s)",
            (ack.command_id, ack.device_id, ack.status, late, Jsonb(raw)),
        )
    return outcome


async def apply_state(
    conn: AsyncConnection, state: StateIn, raw: dict[str, Any]
) -> None:
    async with conn.transaction():
        await conn.execute(
            "INSERT INTO device_state (device_id, mode, relay_state, last_command_id,"
            " reported_at, received_at, payload)"
            " VALUES (%s, %s, %s, %s, %s, now(), %s)"
            " ON CONFLICT (device_id) DO UPDATE SET mode = EXCLUDED.mode,"
            " relay_state = EXCLUDED.relay_state,"
            " last_command_id = EXCLUDED.last_command_id,"
            " reported_at = EXCLUDED.reported_at,"
            " received_at = EXCLUDED.received_at, payload = EXCLUDED.payload",
            (
                state.device_id,
                state.mode,
                state.relay_state,
                state.last_command_id,
                state.reported_at,
                Jsonb(raw),
            ),
        )
        if state.last_command_id is not None:
            # State confirms what the device reports; it does not replace the ACK.
            await conn.execute(
                "UPDATE command SET state_confirmed_at ="
                " COALESCE(state_confirmed_at, now())"
                " WHERE command_id = %s AND device_id = %s",
                (state.last_command_id, state.device_id),
            )
        await conn.execute(
            "INSERT INTO command_event (command_id, device_id, kind, payload)"
            " VALUES (%s, %s, 'state', %s)",
            (state.last_command_id, state.device_id, Jsonb(raw)),
        )


async def get_device_state(
    conn: AsyncConnection, device_id: str
) -> dict[str, Any] | None:
    cursor = await conn.execute(
        "SELECT device_id, mode, relay_state, last_command_id, reported_at,"
        " received_at FROM device_state WHERE device_id = %s",
        (device_id,),
    )
    return await cursor.fetchone()
