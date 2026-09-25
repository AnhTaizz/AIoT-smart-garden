"""Deterministic PostgreSQL tests for G02 deadline races.

These call the repository with a real database connection. The test transaction
holds the command row lock while moving expires_at, so the background sweeper
cannot decide the result for the code under test.
"""

import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone

import psycopg
import pytest
from psycopg.rows import dict_row

from app import repository
from app.schemas import AckIn, StateIn
from helpers import API

pytestmark = pytest.mark.skipif(not API, reason="E2E_API_BASE_URL not set")


async def connect():
    return await psycopg.AsyncConnection.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "smart_garden"),
        user=os.getenv("DB_USER", "smart_garden"),
        password=os.getenv("DB_PASSWORD", ""),
        row_factory=dict_row,
    )


def ack_payload(command_id, device_id, boot_id, status="applied"):
    return {
        "schema": "ack-v1",
        "command_id": str(command_id),
        "device_id": device_id,
        "boot_id": boot_id,
        "status": status,
        "reason": None,
        "clock_synced": True,
        "acked_at": datetime.now(timezone.utc).isoformat(),
    }


def state_payload(command_id, device_id, boot_id, command_sequence):
    return {
        "schema": "state-v1",
        "device_id": device_id,
        "boot_id": boot_id,
        "state_sequence": 1,
        "mode": "MANUAL",
        "relay_state": "on",
        "last_command_id": str(command_id),
        "last_command_sequence": command_sequence,
        "clock_synced": True,
        "reported_at": datetime.now(timezone.utc).isoformat(),
        "uptime_ms": 1000,
    }


async def insert_pending(conn, expires_at):
    command_id = uuid.uuid4()
    device_id = f"deadline_{uuid.uuid4().hex[:8]}"
    boot_id = f"boot_{uuid.uuid4().hex[:8]}"
    command_sequence = 1
    await conn.execute(
        "INSERT INTO command (command_id, device_id, command_sequence, action,"
        " params, target_boot_id, status, expires_at, published_at)"
        " VALUES (%s, %s, %s, 'pump_on', %s, %s, 'pending', %s, now())",
        (
            command_id,
            device_id,
            command_sequence,
            '{"duration_seconds": 5}',
            boot_id,
            expires_at,
        ),
    )
    await conn.commit()
    return command_id, device_id, boot_id, command_sequence


async def command_row(conn, command_id):
    cursor = await conn.execute(
        "SELECT status, device_ack, late_ack, state_confirmed_at,"
        " confirmed_relay_state, confirmed_boot_id"
        " FROM command WHERE command_id = %s",
        (command_id,),
    )
    return await cursor.fetchone()


async def state_row(conn, device_id):
    cursor = await conn.execute(
        "SELECT relay_state, last_command_id FROM device_state WHERE device_id = %s",
        (device_id,),
    )
    return await cursor.fetchone()


def test_state_second_after_deadline_times_out_and_keeps_evidence():
    async def scenario():
        async with await connect() as conn:
            values = await insert_pending(
                conn, datetime.now(timezone.utc) + timedelta(minutes=1)
            )
            command_id, device_id, boot_id, command_sequence = values
            ack_raw = ack_payload(command_id, device_id, boot_id)
            await repository.apply_ack(conn, AckIn.model_validate(ack_raw), ack_raw)

            async with conn.transaction():
                await conn.execute(
                    "UPDATE command SET expires_at = clock_timestamp()"
                    " WHERE command_id = %s",
                    (command_id,),
                )
                before = await command_row(conn, command_id)
                assert before["status"] == "pending"
                state_raw = state_payload(
                    command_id, device_id, boot_id, command_sequence
                )
                await repository.apply_state(
                    conn, StateIn.model_validate(state_raw), state_raw
                )

            final = await command_row(conn, command_id)
            current = await state_row(conn, device_id)
            assert final["status"] == "timeout"
            assert final["device_ack"] == "applied"
            assert final["confirmed_relay_state"] == "on"
            assert final["confirmed_boot_id"] == boot_id
            assert final["state_confirmed_at"] is not None
            assert current["relay_state"] == "on"
            assert str(current["last_command_id"]) == str(command_id)

    asyncio.run(scenario())


def test_ack_second_after_deadline_times_out_and_keeps_earlier_state():
    async def scenario():
        async with await connect() as conn:
            values = await insert_pending(
                conn, datetime.now(timezone.utc) + timedelta(minutes=1)
            )
            command_id, device_id, boot_id, command_sequence = values
            state_raw = state_payload(command_id, device_id, boot_id, command_sequence)
            await repository.apply_state(
                conn, StateIn.model_validate(state_raw), state_raw
            )

            async with conn.transaction():
                await conn.execute(
                    "UPDATE command SET expires_at = clock_timestamp()"
                    " WHERE command_id = %s",
                    (command_id,),
                )
                before = await command_row(conn, command_id)
                assert before["status"] == "pending"
                ack_raw = ack_payload(command_id, device_id, boot_id)
                await repository.apply_ack(
                    conn, AckIn.model_validate(ack_raw), ack_raw
                )

            final = await command_row(conn, command_id)
            assert final["status"] == "timeout"
            assert final["late_ack"] == "applied"
            assert final["confirmed_relay_state"] == "on"
            assert final["confirmed_boot_id"] == boot_id

    asyncio.run(scenario())


def test_both_evidence_before_deadline_applies():
    async def scenario():
        async with await connect() as conn:
            values = await insert_pending(
                conn, datetime.now(timezone.utc) + timedelta(minutes=1)
            )
            command_id, device_id, boot_id, command_sequence = values
            ack_raw = ack_payload(command_id, device_id, boot_id)
            await repository.apply_ack(conn, AckIn.model_validate(ack_raw), ack_raw)
            state_raw = state_payload(command_id, device_id, boot_id, command_sequence)
            await repository.apply_state(
                conn, StateIn.model_validate(state_raw), state_raw
            )

            final = await command_row(conn, command_id)
            assert final["status"] == "applied"
            assert final["device_ack"] == "applied"
            assert final["confirmed_relay_state"] == "on"

    asyncio.run(scenario())
