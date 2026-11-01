"""Actual DB/MQTT/ACK loop, deterministic AI replies (no GPU claim)."""
import asyncio
from dataclasses import replace
import json
import os
from uuid import uuid4
from unittest.mock import patch

import httpx
import pytest
from psycopg.types.json import Jsonb

from app.config import Settings
from app.db import create_pool
from app.irrigation import evaluate, Policy
from app.main import app, issue_command, create_command
from app.mqtt_bridge import MqttBridge
from app.schemas import CommandCreate
from starlette.requests import Request
from helpers import API, FakeDevice, MQTT_HOST, MQTT_PORT

pytestmark = pytest.mark.skipif(not API, reason="Requires running Compose stack")


@pytest.mark.parametrize("scenario", ["water", "no_water", "invalid", "cooldown", "over_limit", "manual_race", "command_timeout", "lease_expired"])
def test_supervisor_closes_the_loop(scenario):
    async def run():
        settings = replace(Settings.from_env(), mqtt_host=MQTT_HOST, mqtt_port=MQTT_PORT, mqtt_client_id="auto_test_" + uuid4().hex[:8])
        pool = create_pool(settings)
        await pool.open(wait=True)
        bridge = MqttBridge(settings, asyncio.get_running_loop(), asyncio.Queue(maxsize=100))
        bridge.start()
        try:
            for _ in range(100):
                if bridge.is_connected(): break
                await asyncio.sleep(.05)
            assert bridge.is_connected()
            with FakeDevice(auto_respond=scenario != "command_timeout") as device:
                device.announce()
                device.publish_telemetry()
                device.wait_for_count(1)
                policy = Policy(crop="Cây mô phỏng", stage="Thử nghiệm", substrate="Giả lập", moisture_stop_pct=80,
                                max_pulse_seconds=2, daily_budget_seconds=10)
                async with pool.connection() as conn:
                    cursor = await conn.execute(
                        "INSERT INTO irrigation_profile(device_id,enabled,policy,lease_token,lease_until,last_attempt,next_evaluation) "
                        "VALUES(%s,true,%s,%s,now()+interval '180 seconds',CASE WHEN %s THEN now() ELSE NULL END,now()+interval '1 hour') RETURNING *",
                        (device.device_id, Jsonb(policy.model_dump()), uuid4(), scenario == "cooldown"))
                    profile = await cursor.fetchone()
                request = Request({"type": "http", "app": app})

                async def reply(_request):
                    if scenario == "manual_race":
                        await create_command(device.device_id, CommandCreate(action="pump_off"), request)
                    if scenario == "lease_expired":
                        async with pool.connection() as conn:
                            await conn.execute("UPDATE irrigation_profile SET lease_until=now()-interval '1 second' WHERE device_id=%s", (device.device_id,))
                    answer = "not json" if scenario == "invalid" else json.dumps({"water": scenario != "no_water", "duration_seconds": 0 if scenario == "no_water" else (5 if scenario == "over_limit" else 1), "reason": "AI giả lập cho kiểm thử"})
                    return httpx.Response(200, json={"response": answer})

                async with httpx.AsyncClient(transport=httpx.MockTransport(reply)) as client:
                    with patch.object(app.state, "settings", settings, create=True), patch.object(app.state, "pool", pool, create=True), patch.object(app.state, "bridge", bridge, create=True), patch.object(app.state, "chat_client", client, create=True), patch.object(app.state, "issue_irrigation_command", issue_command, create=True):
                        await evaluate(app, profile)
                        async with pool.connection() as conn:
                            cursor = await conn.execute("SELECT * FROM irrigation_decision WHERE device_id=%s ORDER BY created_at", (device.device_id,))
                            rows = await cursor.fetchall()
                        if scenario in ("water", "command_timeout"):
                            assert rows[0]["status"] == "sent"
                            command_id = str(rows[0]["command_id"])
                            device.next_control(command_id)
                            result = device.wait_status(command_id, "applied" if scenario == "water" else "timeout")
                            assert result["status"] == ("applied" if scenario == "water" else "timeout")
                            if scenario == "command_timeout":
                                async with pool.connection() as conn:
                                    await conn.execute("UPDATE irrigation_profile SET lease_until=now()+interval '180 seconds' WHERE device_id=%s", (device.device_id,))
                                await evaluate(app, profile)
                                async with pool.connection() as conn:
                                    row = await (await conn.execute("SELECT enabled FROM irrigation_profile WHERE device_id=%s", (device.device_id,))).fetchone()
                                assert row["enabled"] is False
                            else:
                                assert result["confirmed_relay_state"] == "on"
                        else:
                            assert rows[0]["status"] == {"no_water": "no_water", "invalid": "error", "manual_race": "cancelled", "lease_expired": "cancelled"}.get(scenario, "blocked")
                            assert all(item["reserved_seconds"] == 0 for item in rows)
                            commands = device.history()  # Telemetry remains available.
                            assert commands["count"] == 1
                            while not device.control.empty():
                                assert device.control.get()["action"] == "pump_off"
        finally:
            if 'device' in locals():
                async with pool.connection() as conn:
                    await conn.execute("UPDATE irrigation_profile SET enabled=false WHERE device_id=%s", (device.device_id,))
            bridge.stop()
            await pool.close()
    asyncio.run(run())
