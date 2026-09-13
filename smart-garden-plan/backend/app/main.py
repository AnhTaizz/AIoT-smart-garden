import asyncio
import logging
import os
from typing import Any

import psycopg
from fastapi import FastAPI
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

app = FastAPI(title="Smart Garden API")


def _database_connection_parameters() -> dict[str, Any]:
    """Build connection parameters without placing credentials in a URL."""
    return {
        "host": os.getenv("DB_HOST", "postgres"),
        "port": int(os.getenv("DB_PORT", "5432")),
        "dbname": os.getenv("DB_NAME", "smart_garden"),
        "user": os.getenv("DB_USER", "smart_garden"),
        "password": os.getenv("DB_PASSWORD", ""),
        "connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT_SECONDS", "2")),
    }


@app.get("/health")
async def health() -> dict[str, str]:
    """Report whether the API process can serve requests."""
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> JSONResponse:
    """Report readiness after executing a real PostgreSQL query."""
    try:
        connection_parameters = _database_connection_parameters()
        timeout_seconds = max(
            float(connection_parameters["connect_timeout"]),
            0.1,
        )
        async with asyncio.timeout(timeout_seconds):
            connection = await psycopg.AsyncConnection.connect(
                **connection_parameters
            )
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
