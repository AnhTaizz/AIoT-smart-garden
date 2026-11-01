"""Shared fixtures for unit tests that run the FastAPI app without DB/MQTT.

The auth session store is replaced by an in-memory fake with the same rules as
the SQL in app/repository.py (hash lookup, credential match, not revoked, not
expired). The real SQL is covered by tests/e2e against PostgreSQL.
"""

from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app import repository
from app.auth import hash_password
from app.config import Settings
from app.main import app

OPERATOR = "operator1"
PASSWORD = "correct horse battery"
# Cheapest accepted scrypt cost keeps the suite fast; production uses 2^17.
PASSWORD_HASH = hash_password(PASSWORD, log2_n=14)


class FakePool:
    unavailable = False
    calls = 0

    @asynccontextmanager
    async def connection(self):
        self.calls += 1
        if self.unavailable:
            from psycopg_pool import PoolTimeout

            raise PoolTimeout()
        yield object()


class FakeSessions:
    def __init__(self):
        self.rows: dict[bytes, dict] = {}

    async def create(self, _conn, token_hash, username, role, credential_id, ttl_seconds):
        row = {
            "username": username, "role": role, "credential_id": credential_id,
            "expires_at": datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds),
            "revoked_at": None,
        }
        self.rows[token_hash] = row
        return row

    async def get_active(self, _conn, token_hash, credential_id):
        row = self.rows.get(token_hash)
        if (
            row is None or row["credential_id"] != credential_id or row["revoked_at"]
            or row["expires_at"] <= datetime.now(timezone.utc)
        ):
            return None
        return row

    async def revoke(self, _conn, token_hash):
        if token_hash in self.rows:
            self.rows[token_hash]["revoked_at"] = datetime.now(timezone.utc)

    def expire_all(self):
        for row in self.rows.values():
            row["expires_at"] = datetime.now(timezone.utc) - timedelta(seconds=1)


def settings_with(**overrides) -> Settings:
    base = replace(
        Settings.from_env(), operator_username=OPERATOR, operator_password_hash=PASSWORD_HASH,
        operator_role="operator",
    )
    return replace(base, **overrides)


@pytest.fixture
def api(monkeypatch):
    """TestClient with fake pool/bridge/session store; no lifespan is entered."""
    sessions = FakeSessions()
    bridge = MagicMock()
    bridge.is_connected.return_value = False
    pool = FakePool()
    monkeypatch.setattr(app.state, "settings", settings_with(), raising=False)
    monkeypatch.setattr(app.state, "bridge", bridge, raising=False)
    monkeypatch.setattr(app.state, "pool", pool, raising=False)
    monkeypatch.setattr(app.state, "limiters", None, raising=False)
    monkeypatch.setattr(repository, "create_session", sessions.create)
    monkeypatch.setattr(repository, "get_active_session", sessions.get_active)
    monkeypatch.setattr(repository, "revoke_session", sessions.revoke)
    client = TestClient(app)

    class Api:
        pass

    env = Api()
    env.client, env.bridge, env.pool, env.sessions = client, bridge, pool, sessions

    def configure(**overrides):
        app.state.settings = settings_with(**overrides)
        app.state.limiters = None

    def login(username=OPERATOR, password=PASSWORD):
        response = client.post("/auth/login", json={"username": username, "password": password})
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    env.configure, env.login = configure, login
    yield env
    client.close()
