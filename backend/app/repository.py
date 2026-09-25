"""SQL for telemetry, rejected messages and the command lifecycle.

The command rules implemented here follow docs/INTERFACES.md: a command only
becomes `applied` with both a device ACK and a state message proving the relay
matches the action, evidence is kept per command, and messages from a dead boot
can never apply a command or drag the device state backwards.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg import AsyncConnection
from psycopg.types.json import Jsonb

from .schemas import EXPECTED_RELAY_STATE, AckIn, PayloadError, StateIn, TelemetryIn

RAW_PAYLOAD_LIMIT = 4096
REBOOT_REASON = "backend:device_rebooted"
PUBLISH_FAILED_REASON = "backend:publish_failed"

COMMAND_COLUMNS = (
    "command_id, device_id, command_sequence, action, params, target_boot_id,"
    " status, device_ack, reason, created_at, expires_at, published_at, acked_at,"
    " ack_boot_id, state_confirmed_at, confirmed_relay_state,"
    " confirmed_state_sequence, confirmed_boot_id, finalized_at, late_ack,"
    " late_ack_at"
)
TELEMETRY_COLUMNS = (
    "id, device_id, boot_id, sequence, clock_synced, measured_at, received_at,"
    " uptime_ms, temperature_c, air_humidity_pct, soil_moisture_pct,"
    " sensor_status, simulated, payload_schema"
)
STATE_COLUMNS = (
    "device_id, boot_id, state_sequence, mode, relay_state, last_command_id,"
    " last_command_sequence, clock_synced, reported_at, received_at"
)


# --- telemetry -------------------------------------------------------------


async def insert_telemetry(
    conn: AsyncConnection, topic: str, telemetry: TelemetryIn, raw: dict[str, Any]
) -> int | None:
    """Store one reading. Returns None when it is a duplicate we ignore."""
    cursor = await conn.execute(
        "INSERT INTO telemetry (device_id, boot_id, sequence, clock_synced,"
        " measured_at, uptime_ms, temperature_c, air_humidity_pct,"
        " soil_moisture_pct, sensor_status, simulated, payload_schema, topic,"
        " raw_payload)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
        " ON CONFLICT (device_id, boot_id, sequence) DO NOTHING"
        " RETURNING id",
        (
            telemetry.device_id,
            telemetry.boot_id,
            telemetry.sequence,
            telemetry.clock_synced,
            telemetry.measured_at,
            telemetry.uptime_ms,
            telemetry.temperature_c,
            telemetry.air_humidity_pct,
            telemetry.soil_moisture_pct,
            Jsonb(telemetry.sensor_status.model_dump()),
            telemetry.simulated,
            telemetry.payload_schema,
            topic,
            Jsonb(raw),
        ),
    )
    row = await cursor.fetchone()
    return None if row is None else row["id"]


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
    """The most recent `limit` rows by server receive time, newest first.

    received_at is the M1 time axis: a device with an unsynced clock reports no
    measured_at at all, so ordering must not depend on it.
    """
    cursor = await conn.execute(
        f"SELECT {TELEMETRY_COLUMNS} FROM telemetry"
        " WHERE device_id = %s"
        " AND (%s::timestamptz IS NULL OR received_at >= %s)"
        " AND (%s::timestamptz IS NULL OR received_at <= %s)"
        " ORDER BY received_at DESC, id DESC LIMIT %s",
        (device_id, since, since, until, until, limit),
    )
    return await cursor.fetchall()


# --- commands --------------------------------------------------------------


async def current_boot_id(conn: AsyncConnection, device_id: str) -> str | None:
    cursor = await conn.execute(
        "SELECT boot_id FROM device_state WHERE device_id = %s", (device_id,)
    )
    row = await cursor.fetchone()
    return None if row is None else row["boot_id"]


async def allocate_command_sequence(conn: AsyncConnection, device_id: str) -> int:
    """Hand out the next per-device sequence atomically and durably."""
    cursor = await conn.execute(
        "INSERT INTO device_command_counter (device_id, last_sequence)"
        " VALUES (%s, 1)"
        " ON CONFLICT (device_id) DO UPDATE"
        " SET last_sequence = device_command_counter.last_sequence + 1,"
        " updated_at = now()"
        " RETURNING last_sequence",
        (device_id,),
    )
    row = await cursor.fetchone()
    return row["last_sequence"]


async def insert_command(
    conn: AsyncConnection,
    command_id: UUID,
    device_id: str,
    command_sequence: int,
    action: str,
    params: dict[str, Any],
    target_boot_id: str | None,
    timeout_seconds: int,
) -> dict[str, Any]:
    cursor = await conn.execute(
        "INSERT INTO command (command_id, device_id, command_sequence, action,"
        " params, target_boot_id, status, expires_at)"
        " VALUES (%s, %s, %s, %s, %s, %s, 'pending',"
        " now() + make_interval(secs => %s))"
        f" RETURNING {COMMAND_COLUMNS}",
        (
            command_id,
            device_id,
            command_sequence,
            action,
            Jsonb(params),
            target_boot_id,
            timeout_seconds,
        ),
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
        "UPDATE command SET status = 'rejected', reason = %s, finalized_at = now()"
        " WHERE command_id = %s AND status = 'pending'"
        f" RETURNING {COMMAND_COLUMNS}",
        (PUBLISH_FAILED_REASON, command_id),
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
        " ORDER BY command_sequence DESC LIMIT %s",
        (device_id, limit),
    )
    return await cursor.fetchall()


async def _log_event(
    conn: AsyncConnection,
    command_id: UUID | None,
    device_id: str,
    kind: str,
    boot_id: str,
    outcome: str,
    ack_status: str | None,
    late: bool,
    raw: dict[str, Any],
) -> None:
    await conn.execute(
        "INSERT INTO command_event (command_id, device_id, kind, boot_id, outcome,"
        " ack_status, late, payload) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (
            command_id,
            device_id,
            kind,
            boot_id,
            outcome,
            ack_status,
            late,
            Jsonb(raw),
        ),
    )


async def _finalize_if_confirmed(conn: AsyncConnection, command: dict[str, Any]) -> bool:
    """Set `applied` when ACK and state evidence agree on the same boot."""
    if command["status"] != "pending":
        return False
    if command["device_ack"] != "applied" or command["state_confirmed_at"] is None:
        return False
    if command["ack_boot_id"] != command["confirmed_boot_id"]:
        return False
    await conn.execute(
        "UPDATE command SET status = 'applied', finalized_at = now()"
        " WHERE command_id = %s AND status = 'pending'",
        (command["command_id"],),
    )
    return True


async def apply_ack(conn: AsyncConnection, ack: AckIn, raw: dict[str, Any]) -> str:
    """Advance a command from a device ACK and return the outcome for logs."""
    async with conn.transaction():
        cursor = await conn.execute(
            f"SELECT {COMMAND_COLUMNS}, expires_at < now() AS expired"
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
                    "UPDATE command SET status = 'timeout',"
                    " finalized_at = expires_at WHERE command_id = %s",
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
            elif not await _ack_boot_is_current(conn, ack, command):
                # An ACK from a boot that has already been replaced proves
                # nothing about the device running now.
                outcome = "stale_boot"
            elif ack.status == "accepted":
                await conn.execute(
                    "UPDATE command SET device_ack = 'accepted', acked_at = now(),"
                    " ack_boot_id = %s WHERE command_id = %s",
                    (ack.boot_id, ack.command_id),
                )
                outcome = "accepted"
            elif ack.status == "rejected":
                await conn.execute(
                    "UPDATE command SET status = 'rejected', device_ack = 'rejected',"
                    " reason = %s, acked_at = now(), ack_boot_id = %s,"
                    " finalized_at = now() WHERE command_id = %s",
                    (ack.reason, ack.boot_id, ack.command_id),
                )
                outcome = "rejected"
            elif (
                command["confirmed_boot_id"] is not None
                and command["confirmed_boot_id"] != ack.boot_id
            ):
                outcome = "evidence_boot_mismatch"
            else:
                await conn.execute(
                    "UPDATE command SET device_ack = 'applied', acked_at = now(),"
                    " ack_boot_id = %s WHERE command_id = %s",
                    (ack.boot_id, ack.command_id),
                )
                command = {**command, "device_ack": "applied", "ack_boot_id": ack.boot_id}
                confirmed = await _finalize_if_confirmed(conn, command)
                outcome = "applied" if confirmed else "awaiting_state_evidence"

        await _log_event(
            conn,
            ack.command_id,
            ack.device_id,
            "ack",
            ack.boot_id,
            outcome,
            ack.status,
            late,
            raw,
        )
    return outcome


async def _ack_boot_is_current(
    conn: AsyncConnection, ack: AckIn, command: dict[str, Any]
) -> bool:
    """An ACK counts only if it comes from the boot the command targets."""
    if command["target_boot_id"] is not None:
        return ack.boot_id == command["target_boot_id"]
    # pump_off carries no target boot: accept the current boot, or a boot the
    # backend has not seen yet (the device may have just restarted).
    current = await current_boot_id(conn, command["device_id"])
    if current is None or current == ack.boot_id:
        return True
    cursor = await conn.execute(
        "SELECT 1 FROM device_boot WHERE device_id = %s AND boot_id = %s",
        (command["device_id"], ack.boot_id),
    )
    return await cursor.fetchone() is None


async def apply_state(
    conn: AsyncConnection, state: StateIn, raw: dict[str, Any]
) -> str:
    """Record reported state, handle reboots and confirm matching commands."""
    async with conn.transaction():
        cursor = await conn.execute(
            "SELECT boot_id, state_sequence FROM device_state"
            " WHERE device_id = %s FOR UPDATE",
            (state.device_id,),
        )
        stored = await cursor.fetchone()

        cursor = await conn.execute(
            "INSERT INTO device_boot (device_id, boot_id) VALUES (%s, %s)"
            " ON CONFLICT (device_id, boot_id) DO NOTHING RETURNING boot_id",
            (state.device_id, state.boot_id),
        )
        boot_is_new = await cursor.fetchone() is not None

        if stored is None:
            # First time the backend hears from this device: not a reboot.
            outcome = "first_state"
            await _upsert_state(conn, state, raw)
        elif stored["boot_id"] == state.boot_id:
            if state.state_sequence > stored["state_sequence"]:
                outcome = "updated"
                await _upsert_state(conn, state, raw)
            else:
                outcome = "ignored_old_sequence"
        elif boot_is_new:
            outcome = "reboot"
            await _upsert_state(conn, state, raw)
            cancelled = await conn.execute(
                "UPDATE command SET status = 'timeout', reason = %s,"
                " finalized_at = now() WHERE device_id = %s AND status = 'pending'"
                " AND target_boot_id = %s RETURNING command_id",
                (REBOOT_REASON, state.device_id, stored["boot_id"]),
            )
            if await cancelled.fetchall():
                outcome = "reboot_cancelled_pending"
        else:
            # A late message from a boot we already replaced: usable as command
            # evidence, but it must not drag the device state back.
            outcome = "stale_boot_state"

        evidence = await _record_evidence(conn, state)
        await _log_event(
            conn,
            state.last_command_id,
            state.device_id,
            "state",
            state.boot_id,
            f"{outcome}/{evidence}" if evidence else outcome,
            None,
            outcome == "stale_boot_state",
            raw,
        )
    return outcome


async def _upsert_state(
    conn: AsyncConnection, state: StateIn, raw: dict[str, Any]
) -> None:
    await conn.execute(
        "INSERT INTO device_state (device_id, boot_id, state_sequence, mode,"
        " relay_state, last_command_id, last_command_sequence, clock_synced,"
        " reported_at, received_at, payload)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, now(), %s)"
        " ON CONFLICT (device_id) DO UPDATE SET boot_id = EXCLUDED.boot_id,"
        " state_sequence = EXCLUDED.state_sequence, mode = EXCLUDED.mode,"
        " relay_state = EXCLUDED.relay_state,"
        " last_command_id = EXCLUDED.last_command_id,"
        " last_command_sequence = EXCLUDED.last_command_sequence,"
        " clock_synced = EXCLUDED.clock_synced,"
        " reported_at = EXCLUDED.reported_at,"
        " received_at = EXCLUDED.received_at, payload = EXCLUDED.payload",
        (
            state.device_id,
            state.boot_id,
            state.state_sequence,
            state.mode,
            state.relay_state,
            state.last_command_id,
            state.last_command_sequence,
            state.clock_synced,
            state.reported_at,
            Jsonb(raw),
        ),
    )


async def _record_evidence(conn: AsyncConnection, state: StateIn) -> str | None:
    """Store per-command proof that the relay matched the requested action."""
    if state.last_command_id is None:
        return None

    cursor = await conn.execute(
        f"SELECT {COMMAND_COLUMNS} FROM command WHERE command_id = %s FOR UPDATE",
        (state.last_command_id,),
    )
    command = await cursor.fetchone()
    if command is None or command["device_id"] != state.device_id:
        return "evidence_unknown_command"
    if command["status"] not in ("pending", "timeout"):
        # Applied already has its proof. Rejected/publish-failed commands cannot
        # acquire proof later and are still preserved in command_event.
        return "ignored_final"
    if EXPECTED_RELAY_STATE.get(command["action"]) != state.relay_state:
        # relay_state contradicts the action, so this is not evidence for it.
        return "evidence_relay_mismatch"
    if command["target_boot_id"] is not None and command["target_boot_id"] != state.boot_id:
        return "evidence_boot_mismatch"
    if command["ack_boot_id"] is not None and command["ack_boot_id"] != state.boot_id:
        return "evidence_boot_mismatch"
    if command["state_confirmed_at"] is not None:
        return "evidence_already_recorded"

    await conn.execute(
        "UPDATE command SET state_confirmed_at = now(), confirmed_relay_state = %s,"
        " confirmed_state_sequence = %s, confirmed_boot_id = %s"
        " WHERE command_id = %s",
        (
            state.relay_state,
            state.state_sequence,
            state.boot_id,
            state.last_command_id,
        ),
    )
    command = {
        **command,
        "state_confirmed_at": datetime.now(),
        "confirmed_boot_id": state.boot_id,
    }
    if command["status"] == "timeout":
        # Preserve late proof on the command, but never resurrect a timeout.
        return "late_evidence_recorded"
    confirmed = await _finalize_if_confirmed(conn, command)
    return "evidence_applied" if confirmed else "evidence_awaiting_ack"


async def get_device_state(
    conn: AsyncConnection, device_id: str, stale_seconds: int
) -> dict[str, Any] | None:
    cursor = await conn.execute(
        f"SELECT {STATE_COLUMNS},"
        " now() - received_at > make_interval(secs => %s) AS stale"
        " FROM device_state WHERE device_id = %s",
        (stale_seconds, device_id),
    )
    return await cursor.fetchone()
