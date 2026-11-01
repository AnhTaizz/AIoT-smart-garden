"""AI irrigation supervisor. Initial release deliberately supports simulators only."""
import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, model_validator
from psycopg.types.json import Jsonb

from . import repository
from .auth import OperatorDep, SessionDep
from .chat import clean_reply
from .schemas import CommandCreate, DEVICE_ID_PATTERN

logger = logging.getLogger(__name__)
router = APIRouter()
PROMPT_VERSION = "irrigation-decision-v1"


class Policy(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    crop: str = Field(min_length=1, max_length=120)
    stage: str = Field(min_length=1, max_length=120)
    substrate: str = Field(min_length=1, max_length=120)
    moisture_stop_pct: float = Field(ge=0, le=100, allow_inf_nan=False)
    max_pulse_seconds: StrictInt = Field(ge=1, le=60)
    cooldown_seconds: StrictInt = Field(default=300, ge=300, le=86400)
    daily_budget_seconds: StrictInt = Field(ge=1, le=600)
    evaluation_seconds: StrictInt = Field(default=60, ge=30, le=3600)


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: StrictBool
    policy: Policy


class Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    water: StrictBool
    duration_seconds: StrictInt = Field(ge=0, le=60)
    reason: str = Field(min_length=1, max_length=1200)

    @model_validator(mode="after")
    def consistent(self):
        if self.water != (self.duration_seconds > 0):
            raise ValueError("water must match duration_seconds")
        return self


def parse_proposal(value: str) -> Proposal:
    value = clean_reply(value)
    if value.startswith("```json\n") and value.endswith("```"):
        value = value[8:-3].strip()
    return Proposal.model_validate(json.loads(value))


def check_observation(telemetry, state, policy: Policy, stale_seconds: int) -> str | None:
    now = datetime.now(timezone.utc)
    if not telemetry or not state:
        return "Thiếu số đo hoặc trạng thái thiết bị."
    if not telemetry["simulated"]:
        return "Phiên bản này chỉ cho phép AUTO trên simulator, chưa cho phép bơm thật."
    for row in (telemetry, state):
        if row["stale"] or (now - row["received_at"]).total_seconds() > stale_seconds:
            return "Dữ liệu đã cũ; không tưới."
    if telemetry["boot_id"] != state["boot_id"]:
        return "Thiết bị đã đổi boot; cần số đo mới."
    if not telemetry["clock_synced"] or not state["clock_synced"]:
        return "Đồng hồ thiết bị chưa đồng bộ."
    if any(telemetry["sensor_status"].get(key) != "ok" for key in ("soil", "aht20")):
        return "Cảm biến lỗi; không tưới."
    if any(telemetry[key] is None for key in ("soil_moisture_pct", "temperature_c", "air_humidity_pct")):
        return "Thiếu giá trị cảm biến."
    if state["relay_state"] != "off":
        return "Bơm chưa xác nhận tắt."
    if state.get("mode") != "MANUAL":
        return "Thiết bị có bộ điều khiển AUTO riêng; không chạy đồng thời hai bộ quyết định."
    if telemetry["soil_moisture_pct"] >= policy.moisture_stop_pct:
        return "Độ ẩm đã đạt giới hạn ngừng tưới được cấu hình."
    return None


@asynccontextmanager
async def device_lock(pool, device_id):
    # Session lock survives reservation commits; manual STOP and AUTO dispatch
    # serialize on the same key. Never hold this lock while waiting for the AI.
    async with pool.connection() as conn:
        acquired = False
        try:
            for _ in range(40):
                cursor = await conn.execute("SELECT pg_try_advisory_lock(hashtextextended(%s, 0)) AS acquired", ("irrigation:" + device_id,))
                acquired = (await cursor.fetchone())["acquired"]
                await conn.commit()
                if acquired:
                    break
                await asyncio.sleep(.05)
            if not acquired:
                raise HTTPException(503, detail={"code": "irrigation_busy", "message": "Thiết bị đang xử lý lệnh khác; hãy thử lại."})
            yield conn
        finally:
            if acquired:
                await conn.rollback()
                await conn.execute("SELECT pg_advisory_unlock(hashtextextended(%s, 0))", ("irrigation:" + device_id,))
                await conn.commit()


async def disable(conn, device_id, reason="manual"):
    await conn.execute("UPDATE irrigation_profile SET enabled=false, revision=revision+1, last_status=%s WHERE device_id=%s", (reason, device_id))
    await conn.commit()


async def snapshot(conn, app, device_id):
    stale = app.state.settings.telemetry_stale_seconds
    return (await repository.latest_telemetry(conn, device_id, stale),
            await repository.get_device_state(conn, device_id, stale))


async def history(conn, device_id):
    cursor = await conn.execute(
        "SELECT d.*, c.status AS command_status, c.device_ack, c.confirmed_relay_state "
        "FROM irrigation_decision d LEFT JOIN command c ON c.command_id=d.command_id "
        "WHERE d.device_id=%s ORDER BY d.created_at DESC LIMIT 20", (device_id,))
    return await cursor.fetchall()


@router.get("/devices/{device_id}/irrigation")
async def get_profile(device_id: str, request: Request, _session: SessionDep):
    async with request.app.state.pool.connection() as conn:
        cursor = await conn.execute("SELECT device_id,enabled,revision,policy,last_status,last_attempt FROM irrigation_profile WHERE device_id=%s", (device_id,))
        row = await cursor.fetchone()
        return {"profile": row, "decisions": await history(conn, device_id), "execution_scope": "simulator_only"}


@router.put("/devices/{device_id}/irrigation")
async def update_profile(device_id: str, body: ProfileUpdate, request: Request, session: OperatorDep):
    # Operator only: enabling AUTO lets the supervisor publish pump_on, and
    # disabling it publishes pump_off. Anonymous gets 401, a viewer 403.
    import re
    if not re.fullmatch(DEVICE_ID_PATTERN, device_id):
        raise HTTPException(422, "invalid_payload")
    app = request.app
    async with device_lock(app.state.pool, device_id) as conn:
        if body.enabled:
            t, s = await snapshot(conn, app, device_id)
            reason = check_observation(t, s, body.policy, app.state.settings.telemetry_stale_seconds)
            if reason:
                raise HTTPException(409, detail={"code": "irrigation_not_ready", "message": reason})
        await conn.execute(
            "INSERT INTO irrigation_profile(device_id,enabled,policy) VALUES(%s,%s,%s) "
            "ON CONFLICT(device_id) DO UPDATE SET enabled=EXCLUDED.enabled,policy=EXCLUDED.policy,"
            "revision=irrigation_profile.revision+1,next_evaluation=now(),last_status='configured'",
            (device_id, body.enabled, Jsonb(body.policy.model_dump())),)
        await conn.commit()
        # Switching back to MANUAL also requests STOP. The device's timer remains
        # authoritative if MQTT is unavailable; do not claim a physical stop.
        if not body.enabled:
            await app.state.issue_irrigation_command(device_id, CommandCreate(action="pump_off"), request)
    return await get_profile(device_id, request, session)


async def record(conn, device_id, observation, status, reason, proposal=None, reserved=0, command_id=None):
    identifier = uuid4()
    await conn.execute(
        "INSERT INTO irrigation_decision(id,device_id,observation,proposal,status,reason,reserved_seconds,command_id) "
        "VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
        (identifier, device_id, Jsonb(jsonable_encoder(observation)), Jsonb(proposal.model_dump()) if proposal else None,
         status, reason, reserved, command_id),)
    await conn.execute("UPDATE irrigation_profile SET last_status=%s WHERE device_id=%s", (status, device_id))
    await conn.commit()
    return identifier


async def evaluate(app, profile):
    device_id, token = profile["device_id"], profile["lease_token"]
    policy = Policy.model_validate(profile["policy"])
    observation = {}
    try:
        async with app.state.pool.connection() as conn:
            t, s = await snapshot(conn, app, device_id)
            recent = await history(conn, device_id)
        observation = {"telemetry": t, "state": s, "policy": policy.model_dump(), "history": recent[:5], "prompt_version": PROMPT_VERSION}
        reason = check_observation(t, s, policy, app.state.settings.telemetry_stale_seconds)
        if reason:
            async with app.state.pool.connection() as conn:
                await record(conn, device_id, observation, "blocked", reason)
            return
        headers = {"ngrok-skip-browser-warning": "true"}
        if app.state.settings.chat_api_key:
            headers["Authorization"] = "Bearer " + app.state.settings.chat_api_key
        async with asyncio.timeout(app.state.settings.chat_timeout_seconds):
            response = await app.state.chat_client.post(app.state.settings.chat_api_url, headers=headers, timeout=app.state.settings.chat_timeout_seconds, json={
                "messages": [{"role": "system", "content": "Bạn là bộ quyết định tưới thử nghiệm Smart-Garden. Chỉ xuất một JSON đúng schema: {\"water\":true hoặc false,\"duration_seconds\":số nguyên,\"reason\":\"lý do tiếng Việt\"}. Không tưới thì duration_seconds=0. Nếu chưa đủ căn cứ, chọn không tưới. Không vượt max_pulse_seconds. Cân nhắc loại cây, giá thể, số đo và các lần tưới trước. Không giả mạo số đo. Không xuất Markdown hoặc suy nghĩ. /no_think"},
                             {"role": "user", "content": json.dumps(jsonable_encoder(observation), ensure_ascii=False)}],
                "temperature": 0, "max_tokens": 512})
        response.raise_for_status()
        raw = response.json()["response"]
        observation["model_response"] = str(raw)[:4000]
        proposal = parse_proposal(raw)
        async with device_lock(app.state.pool, device_id) as conn:
            cursor = await conn.execute("SELECT * FROM irrigation_profile WHERE device_id=%s", (device_id,))
            current = await cursor.fetchone()
            if not current["enabled"] or current["revision"] != profile["revision"] or current["lease_token"] != token or not current["lease_until"] or current["lease_until"] <= datetime.now(timezone.utc):
                await record(conn, device_id, observation, "cancelled", "Cấu hình/chế độ đã đổi khi chờ AI.", proposal)
                return
            fresh_t, fresh_s = await snapshot(conn, app, device_id)
            reason = check_observation(fresh_t, fresh_s, policy, app.state.settings.telemetry_stale_seconds)
            if (datetime.now(timezone.utc) - t["received_at"]).total_seconds() > app.state.settings.telemetry_stale_seconds:
                reason = "Số đo mà AI dùng đã hết hạn khi model trả lời; cần đánh giá lại."
            if fresh_s and fresh_s["boot_id"] != s["boot_id"]:
                reason = "Thiết bị đã khởi động lại khi chờ AI."
            commands = await repository.list_commands(conn, device_id, 1)
            if commands and commands[0]["status"] in ("pending", "timeout", "rejected"):
                reason = "Lệnh trước chưa rõ kết quả hoặc bị từ chối; cần chuyển MANUAL kiểm tra."
                await disable(conn, device_id, "command_fault")
            if current["last_attempt"] and (datetime.now(timezone.utc) - current["last_attempt"]).total_seconds() < policy.cooldown_seconds:
                reason = "Chưa hết thời gian nghỉ giữa hai lần tưới."
            cursor = await conn.execute("SELECT COALESCE(sum(reserved_seconds),0) AS spent FROM irrigation_decision WHERE device_id=%s AND created_at>now()-interval '24 hours'", (device_id,))
            spent = (await cursor.fetchone())["spent"]
            if proposal.duration_seconds > policy.max_pulse_seconds or spent + proposal.duration_seconds > policy.daily_budget_seconds:
                reason = "Quyết định vượt giới hạn thời lượng hoặc ngân sách 24 giờ."
            if reason or not proposal.water:
                await record(conn, device_id, observation, "blocked" if reason else "no_water", reason or proposal.reason, proposal)
                return
            command_id = uuid4()
            # Durable reservation BEFORE publish: even a crash/timeout consumes
            # the cooldown and budget. Never automatically replay an uncertain ON.
            await conn.execute("UPDATE irrigation_profile SET last_attempt=now() WHERE device_id=%s", (device_id,))
            decision_id = await record(conn, device_id, observation, "reserved", proposal.reason, proposal, proposal.duration_seconds, command_id)
            request = Request({"type": "http", "app": app})
            await app.state.issue_irrigation_command(device_id, CommandCreate(action="pump_on", duration_seconds=proposal.duration_seconds), request, command_id=command_id)
            await conn.execute("UPDATE irrigation_decision SET status='sent' WHERE id=%s", (decision_id,))
            await conn.execute("UPDATE irrigation_profile SET last_status='sent' WHERE device_id=%s", (device_id,))
            await conn.commit()
    except Exception as error:
        logger.warning("AI irrigation refused for %s: %s", device_id, type(error).__name__)
        async with app.state.pool.connection() as conn:
            await record(conn, device_id, observation, "error", "AI/API hoặc thực thi lỗi; không tự thử lại lệnh tưới.")
            await disable(conn, device_id, "error")
    finally:
        async with app.state.pool.connection() as conn:
            await conn.execute("UPDATE irrigation_profile SET lease_until=NULL WHERE device_id=%s AND lease_token=%s", (device_id, token))


async def run(app):
    # Explicit re-arm is required after backend restart.
    while True:
        try:
            async with app.state.pool.connection() as conn:
                await conn.execute("UPDATE irrigation_profile SET enabled=false,revision=revision+1,lease_until=NULL,lease_token=NULL,last_status='restart_requires_manual_arm'")
            break
        except Exception:
            logger.warning("Waiting for irrigation storage before arming supervisor")
            await asyncio.sleep(2)
    while True:
        try:
            token = uuid4()
            async with app.state.pool.connection() as conn:
                cursor = await conn.execute(
                    "UPDATE irrigation_profile SET lease_token=%s,lease_until=now()+interval '180 seconds',"
                    "next_evaluation=now()+((policy->>'evaluation_seconds')::integer * interval '1 second') "
                    "WHERE device_id=(SELECT device_id FROM irrigation_profile WHERE enabled AND next_evaluation<=now() "
                    "AND (lease_until IS NULL OR lease_until<now()) ORDER BY next_evaluation FOR UPDATE SKIP LOCKED LIMIT 1) RETURNING *", (token,))
                profile = await cursor.fetchone()
            if profile:
                await evaluate(app, profile)
        except Exception as error:
            logger.warning("Irrigation supervisor unavailable: %s", type(error).__name__)
        await asyncio.sleep(2)
