import asyncio
import json
import logging
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from typing import Annotated, Any, AsyncIterator, Literal
from uuid import UUID, uuid4

import psycopg
from fastapi import FastAPI, HTTPException, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from . import repository
from .config import Settings
from .db import apply_migrations, create_pool
from .ingest import MessageHandler, consume
from .mqtt_bridge import QUEUE_SIZE, MqttBridge
from .schemas import (
    COMMAND_SCHEMA,
    DEVICE_ID_PATTERN,
    CommandCreate,
    CommandList,
    CommandOut,
    DeviceStateOut,
    LatestTelemetryOut,
    TelemetryOut,
    TelemetryPage,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger(__name__)

MIGRATION_RETRY_SECONDS = 2
TIMEOUT_SWEEP_SECONDS = 1

DevicePath = Annotated[str, Path(pattern=DEVICE_ID_PATTERN)]

# One Vietnamese sentence per machine-readable code, for the dashboard.
ERROR_MESSAGES = {
    "no_telemetry": "Thiết bị chưa có telemetry nào được lưu.",
    "no_state": "Thiết bị chưa gửi trạng thái nào.",
    "command_not_found": "Không tìm thấy lệnh với command_id này.",
    "invalid_payload": "Dữ liệu gửi lên không hợp lệ.",
    "device_boot_unknown": (
        "Backend chưa biết boot_id hiện tại của thiết bị nên chưa gửi được lệnh bật"
        " bơm; chờ thiết bị báo trạng thái."
    ),
    "mqtt_unavailable": "Backend đang mất kết nối tới MQTT broker.",
    "backend_publish_failed": "Backend không publish được lệnh lên MQTT broker.",
    "database_unavailable": "Backend không truy cập được PostgreSQL.",
}


def error_body(code: str, **extra: Any) -> dict[str, Any]:
    detail = {"code": code, "message": ERROR_MESSAGES.get(code, code)}
    detail.update(extra)
    return {"detail": detail}


async def _migrate_until_ready(app: FastAPI) -> None:
    pool = app.state.pool
    while True:
        try:
            async with pool.connection() as conn:
                applied = await apply_migrations(conn)
            logger.info(
                "Database schema ready; applied migrations: %s", applied or "none"
            )
            return
        except Exception as error:
            # Include the failure itself: a migration that cannot apply is
            # otherwise invisible behind a generic retry message.
            logger.warning(
                "Migrations failed (%s: %s); retrying in %ss",
                type(error).__name__,
                error,
                MIGRATION_RETRY_SECONDS,
            )
            await asyncio.sleep(MIGRATION_RETRY_SECONDS)


async def _sweep_timeouts(app: FastAPI) -> None:
    while True:
        try:
            async with app.state.pool.connection() as conn:
                for command_id in await repository.expire_commands(conn):
                    logger.info("Command command_id=%s -> timeout", command_id)
        except Exception:
            logger.warning("Command timeout sweep failed; will retry")
        await asyncio.sleep(TIMEOUT_SWEEP_SECONDS)


async def _run_background(app: FastAPI) -> None:
    # The MQTT subscriber only starts once the tables it writes to exist.
    await _migrate_until_ready(app)
    app.state.bridge.start()
    await asyncio.gather(
        consume(app.state.queue, MessageHandler(app.state.pool)),
        _sweep_timeouts(app),
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = Settings.from_env()
    app.state.settings = settings
    app.state.pool = create_pool(settings)
    # wait=False: /health must keep working while PostgreSQL is down.
    await app.state.pool.open(wait=False)
    app.state.queue = asyncio.Queue(maxsize=QUEUE_SIZE)
    app.state.bridge = MqttBridge(settings, asyncio.get_running_loop(), app.state.queue)
    background = asyncio.create_task(_run_background(app))
    try:
        yield
    finally:
        background.cancel()
        with suppress(asyncio.CancelledError):
            await background
        app.state.bridge.stop()
        await app.state.pool.close()


app = FastAPI(title="Smart Garden API", lifespan=lifespan)


@app.exception_handler(psycopg.Error)
async def database_error_handler(
    _request: Request, error: psycopg.Error
) -> JSONResponse:
    # Keep connection details and SQL errors out of client responses.
    logger.warning("Database error while serving request: %s", type(error).__name__)
    return JSONResponse(status_code=503, content=error_body("database_unavailable"))


@app.exception_handler(HTTPException)
async def http_error_handler(_request: Request, error: HTTPException) -> JSONResponse:
    """Give every error one shape: detail.code plus a Vietnamese message."""
    if isinstance(error.detail, dict) and "code" in error.detail:
        detail = {
            "message": ERROR_MESSAGES.get(error.detail["code"], error.detail["code"]),
            **error.detail,
        }
        content: dict[str, Any] = {"detail": detail}
    else:
        content = error_body(str(error.detail))
    return JSONResponse(
        status_code=error.status_code, content=content, headers=error.headers
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    _request: Request, error: RequestValidationError
) -> JSONResponse:
    fields = sorted(
        {
            ".".join(str(part) for part in item["loc"][1:]) or str(item["loc"][0])
            for item in error.errors()
        }
    )
    return JSONResponse(
        status_code=422, content=error_body("invalid_payload", fields=fields)
    )


@app.get("/health")
async def health() -> dict[str, str]:
    """Report whether the API process can serve requests."""
    return {"status": "ok"}


@app.get("/ready")
async def ready(request: Request) -> JSONResponse:
    """Report readiness after executing a real PostgreSQL query."""
    try:
        settings: Settings = request.app.state.settings
        connection_parameters = settings.database_connection_parameters()
        timeout_seconds = max(
            float(connection_parameters["connect_timeout"]),
            0.1,
        )
        async with asyncio.timeout(timeout_seconds):
            connection = await psycopg.AsyncConnection.connect(**connection_parameters)
            async with connection:
                async with connection.cursor() as cursor:
                    await cursor.execute("SELECT 1")
                    result = await cursor.fetchone()

        if result != (1,):
            raise RuntimeError("PostgreSQL readiness query returned an invalid result")
    except Exception:
        # Keep the log useful without exposing connection details or credentials.
        logger.warning("PostgreSQL readiness check failed")
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "checks": {"postgres": "down"},
            },
        )

    return JSONResponse(
        status_code=200,
        content={
            "status": "ready",
            "checks": {"postgres": "up"},
        },
    )


# --- telemetry -------------------------------------------------------------


@app.get("/devices/{device_id}/latest", response_model=LatestTelemetryOut)
async def get_latest_telemetry(
    device_id: DevicePath, request: Request
) -> dict[str, Any]:
    """Latest telemetry stored in PostgreSQL, by server receive time."""
    stale_seconds = request.app.state.settings.telemetry_stale_seconds
    async with request.app.state.pool.connection() as conn:
        row = await repository.latest_telemetry(conn, device_id, stale_seconds)
    if row is None:
        raise HTTPException(status_code=404, detail="no_telemetry")
    return {**row, "stale_after_seconds": stale_seconds}


@app.get("/devices/{device_id}/telemetry", response_model=TelemetryPage)
async def get_telemetry_history(
    device_id: DevicePath,
    request: Request,
    since: Annotated[datetime | None, Query(alias="from")] = None,
    until: Annotated[datetime | None, Query(alias="to")] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    order: Literal["asc", "desc"] = "asc",
) -> dict[str, Any]:
    """The most recent `limit` rows in [from, to] by received_at, sorted by `order`.

    count == limit only means there may be older rows, it does not prove it.
    """
    for value in (since, until):
        if value is not None and value.tzinfo is None:
            raise HTTPException(
                status_code=422,
                detail={"code": "invalid_payload", "fields": ["from", "to"]},
            )
    async with request.app.state.pool.connection() as conn:
        rows = await repository.telemetry_history(conn, device_id, since, until, limit)
    if order == "asc":
        rows.reverse()
    items = [TelemetryOut.model_validate(row) for row in rows]
    return {"device_id": device_id, "count": len(items), "order": order, "items": items}


# --- commands --------------------------------------------------------------


def _iso(value: datetime) -> str:
    return (
        value.astimezone(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


@app.post("/devices/{device_id}/commands", status_code=202, response_model=CommandOut)
async def create_command(
    device_id: DevicePath, body: CommandCreate, request: Request
) -> dict[str, Any]:
    """Queue a command for the device.

    202 only means the backend stored and published the request; the command
    stays `pending` until the device proves what it did or the deadline passes.
    """
    settings: Settings = request.app.state.settings
    bridge: MqttBridge = request.app.state.bridge
    if (
        body.duration_seconds is not None
        and body.duration_seconds > settings.command_max_duration_seconds
    ):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "invalid_payload",
                "fields": ["duration_seconds"],
                "limit_seconds": settings.command_max_duration_seconds,
            },
        )
    if not bridge.is_connected():
        raise HTTPException(status_code=503, detail="mqtt_unavailable")

    params = (
        {} if body.duration_seconds is None else {"duration_seconds": body.duration_seconds}
    )
    async with request.app.state.pool.connection() as conn:
        target_boot_id = None
        if body.action == "pump_on":
            # pump_on is tied to one boot, so the device can refuse a command
            # aimed at the boot it had before restarting.
            target_boot_id = await repository.current_boot_id(conn, device_id)
            if target_boot_id is None:
                raise HTTPException(status_code=409, detail="device_boot_unknown")

        command_sequence = await repository.allocate_command_sequence(conn, device_id)
        command = await repository.insert_command(
            conn,
            uuid4(),
            device_id,
            command_sequence,
            body.action,
            params,
            target_boot_id,
            settings.command_timeout_seconds,
        )
    # The row is committed here, before the command goes out: a fast device can
    # ACK within a millisecond, and that ACK must not hit a row nobody can see.

    message = {
        "schema": COMMAND_SCHEMA,
        "command_id": str(command["command_id"]),
        "device_id": device_id,
        "command_sequence": command_sequence,
        "action": body.action,
        "params": params,
        "target_boot_id": target_boot_id,
        "issued_at": _iso(command["created_at"]),
        "expires_at": _iso(command["expires_at"]),
    }
    topic = f"garden/{device_id}/control"
    if not bridge.publish(topic, json.dumps(message, separators=(",", ":"))):
        async with request.app.state.pool.connection() as conn:
            await repository.mark_publish_failed(conn, command["command_id"])
        logger.warning("Command publish failed command_id=%s", command["command_id"])
        raise HTTPException(
            status_code=503,
            detail={
                "code": "backend_publish_failed",
                "command_id": message["command_id"],
            },
        )
    async with request.app.state.pool.connection() as conn:
        command = await repository.mark_published(conn, command["command_id"])
    logger.info(
        "Command command_id=%s sequence=%d action=%s target_boot_id=%s -> pending",
        message["command_id"],
        command_sequence,
        body.action,
        target_boot_id,
    )
    return command


@app.get("/devices/{device_id}/commands", response_model=CommandList)
async def list_device_commands(
    device_id: DevicePath,
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, Any]:
    async with request.app.state.pool.connection() as conn:
        await repository.expire_commands(conn)
        items = await repository.list_commands(conn, device_id, limit)
    return {"device_id": device_id, "count": len(items), "items": items}


@app.get("/commands/{command_id}", response_model=CommandOut)
async def get_command(command_id: UUID, request: Request) -> dict[str, Any]:
    async with request.app.state.pool.connection() as conn:
        # Expire on read too, so the status never lags behind the sweeper.
        await repository.expire_commands(conn, command_id)
        command = await repository.get_command(conn, command_id)
    if command is None:
        raise HTTPException(status_code=404, detail="command_not_found")
    return command


@app.get("/devices/{device_id}/state", response_model=DeviceStateOut)
async def get_device_state(device_id: DevicePath, request: Request) -> dict[str, Any]:
    """Last state reported by the device itself, not what was requested."""
    stale_seconds = request.app.state.settings.telemetry_stale_seconds
    async with request.app.state.pool.connection() as conn:
        state = await repository.get_device_state(conn, device_id, stale_seconds)
    if state is None:
        raise HTTPException(status_code=404, detail="no_state")
    return {**state, "stale_after_seconds": stale_seconds}
