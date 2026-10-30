"""BC-02 authentication, authorization and rate limits (no DB/MQTT needed)."""

import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app import repository
from app.auth import credential_id, hash_password, parse_password_hash, verify_password
from app.main import app
from app.ratelimit import SlidingWindowLimiter
from tests.conftest import OPERATOR, PASSWORD, PASSWORD_HASH, settings_with

PROTECTED_READS = [
    "/devices/node_01/latest",
    "/devices/node_01/telemetry",
    "/devices/node_01/state",
    "/devices/node_01/commands",
    f"/commands/{uuid4()}",
    "/control-access",
    "/auth/me",
]


def code(response):
    return response.json()["detail"]["code"]


# --- password hashing ------------------------------------------------------------


def test_scrypt_hash_round_trip_and_format():
    encoded = hash_password("another long secret", log2_n=14)
    assert encoded.startswith("scrypt:14:8:1:") and "$" not in encoded
    assert verify_password("another long secret", encoded)
    assert not verify_password("another long secreT", encoded)
    # Same password, new salt: hashes differ.
    assert hash_password("another long secret", log2_n=14) != encoded


@pytest.mark.parametrize("encoded", [
    "", "plain-password", "scrypt:17:8:1:abc", "bcrypt:14:8:1:AAAAAAAAAAAAAAAAAAAAAA:" + "A" * 43,
    "scrypt:10:8:1:AAAAAAAAAAAAAAAAAAAAAA:" + "A" * 43,  # cost below the minimum
    "scrypt:x:8:1:AAAAAAAAAAAAAAAAAAAAAA:" + "A" * 43,
    "scrypt:14:8:1:AAAA:" + "A" * 43,  # salt too short
])
def test_unusable_hashes_are_rejected(encoded):
    assert parse_password_hash(encoded) is None
    assert not verify_password("anything", encoded)


def test_cli_cost_bounds():
    with pytest.raises(ValueError):
        hash_password("x" * 12, log2_n=12)


# --- configuration fails closed ---------------------------------------------------


@pytest.mark.parametrize("overrides", [
    {"operator_username": ""},
    {"operator_password_hash": ""},
    {"operator_password_hash": "not-a-hash"},
])
def test_missing_or_invalid_account_config_fails_closed(api, overrides):
    headers = api.login()  # a session made while the account was valid
    api.configure(**overrides)
    assert credential_id(app.state.settings) is None
    response = api.client.post("/auth/login", json={"username": OPERATOR, "password": PASSWORD})
    assert response.status_code == 503 and code(response) == "auth_not_configured"
    # Existing tokens stop working too.
    assert api.client.get("/control-access", headers=headers).status_code == 401


def test_unknown_role_is_rejected_at_startup(monkeypatch):
    from app.config import Settings

    monkeypatch.setenv("OPERATOR_ROLE", "admin")
    with pytest.raises(ValueError, match="OPERATOR_ROLE"):
        Settings.from_env()


def test_default_config_has_no_account_and_no_chat_url(monkeypatch):
    from app.config import Settings

    for name in ("OPERATOR_USERNAME", "OPERATOR_PASSWORD_HASH", "CHAT_API_URL"):
        monkeypatch.delenv(name, raising=False)
    settings = Settings.from_env()
    assert credential_id(settings) is None
    assert settings.chat_api_url == ""


def test_changing_password_or_role_revokes_existing_sessions(api):
    headers = api.login()
    api.configure(operator_password_hash=hash_password("a different password", log2_n=14))
    assert api.client.get("/auth/me", headers=headers).status_code == 401
    api.configure()
    headers = api.login()
    api.configure(operator_role="viewer")
    assert api.client.get("/auth/me", headers=headers).status_code == 401


# --- login / me / logout ----------------------------------------------------------


def test_login_success_returns_opaque_expiring_token(api):
    response = api.client.post("/auth/login", json={"username": OPERATOR, "password": PASSWORD})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert len(body["access_token"]) >= 40
    assert body["user"] == {"username": OPERATOR, "role": "operator"}
    expires = datetime.fromisoformat(body["expires_at"])
    assert timedelta(hours=7) < expires - datetime.now(timezone.utc) <= timedelta(hours=8)
    # Only a hash of the token is stored.
    assert body["access_token"].encode() not in api.sessions.rows
    me = api.client.get("/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200 and me.json()["user"]["username"] == OPERATOR


@pytest.mark.parametrize("username, password", [
    (OPERATOR, "wrong password"),
    ("someone", PASSWORD),
    (OPERATOR.upper(), PASSWORD),
])
def test_wrong_credentials_get_401(api, username, password):
    response = api.client.post("/auth/login", json={"username": username, "password": password})
    assert response.status_code == 401
    assert code(response) == "invalid_credentials"
    assert api.sessions.rows == {}


@pytest.mark.parametrize("payload", [
    {}, {"username": OPERATOR}, {"username": "", "password": "x"},
    {"username": OPERATOR, "password": PASSWORD, "role": "operator"},
])
def test_malformed_login_body_is_422(api, payload):
    assert api.client.post("/auth/login", json=payload).status_code == 422


@pytest.mark.parametrize("header", [
    None, "", "Bearer", "Bearer ", "Basic b3A6cHc=", "Token abc", "Bearer " + "x" * 300,
])
def test_missing_or_malformed_token_is_401(api, header):
    headers = {} if header is None else {"Authorization": header}
    response = api.client.get("/control-access", headers=headers)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_unknown_expired_and_revoked_tokens_are_401(api):
    assert code(api.client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})) == "invalid_session"
    expired = api.login()
    api.sessions.expire_all()
    assert api.client.get("/auth/me", headers=expired).status_code == 401
    headers = api.login()
    assert api.client.post("/auth/logout", headers=headers).json() == {"status": "logged_out"}
    response = api.client.get("/auth/me", headers=headers)
    assert response.status_code == 401 and code(response) == "invalid_session"
    # Logging out twice is not possible either.
    assert api.client.post("/auth/logout", headers=headers).status_code == 401


def test_secrets_never_reach_the_logs(api, caplog):
    caplog.set_level(logging.DEBUG)
    api.client.post("/auth/login", json={"username": OPERATOR, "password": "wrong password"})
    token = api.login()["Authorization"].split()[1]
    api.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    text = caplog.text
    for secret in ("wrong password", PASSWORD, token, PASSWORD_HASH):
        assert secret not in text


# --- anonymous access is refused ------------------------------------------------------


@pytest.mark.parametrize("path", PROTECTED_READS)
def test_anonymous_reads_are_401(api, path):
    response = api.client.get(path)
    assert response.status_code == 401
    assert code(response) == "auth_required"


@pytest.mark.parametrize("body", [
    {"action": "pump_on", "duration_seconds": 5},
    {"action": "pump_off"},
    {"action": "pump_on", "duration_seconds": 9999},  # 401 wins over validation
])
def test_anonymous_commands_are_401_and_never_published(api, monkeypatch, body):
    insert = AsyncMock()
    monkeypatch.setattr(repository, "insert_command", insert)
    api.bridge.is_connected.return_value = True
    response = api.client.post("/devices/node_01/commands", json=body)
    assert response.status_code == 401
    insert.assert_not_called()
    api.bridge.publish.assert_not_called()


def test_anonymous_chat_is_401_and_never_reaches_kaggle(api, monkeypatch):
    api.configure(chat_api_url="https://kaggle.test/v1/chat/completions")
    upstream = AsyncMock()
    monkeypatch.setattr(app.state, "chat_client", upstream, raising=False)
    response = api.client.post("/chat", json={"message": "Xin chào"})
    assert response.status_code == 401
    upstream.post.assert_not_called()


@pytest.mark.parametrize("path", ["/health", "/ready"])
def test_health_endpoints_stay_public_and_minimal(api, path, monkeypatch):
    if path == "/ready":
        # Unreachable DB: /ready reports down without leaking any details.
        api.configure(db_host="127.0.0.1", db_port=1, db_connect_timeout_seconds=1)
        response = api.client.get(path)
        assert response.status_code == 503
        assert response.json() == {"status": "not_ready", "checks": {"postgres": "down"}}
    else:
        assert api.client.get(path).json() == {"status": "ok"}


# --- authorization ------------------------------------------------------------------------


def test_operator_may_control_even_through_tunnel_headers(api):
    headers = api.login()
    for extra in ({}, {"Cf-Connecting-Ip": "1.1.1.1", "Cf-Ray": "abc-SIN", "X-Forwarded-For": "1.1.1.1"}):
        access = api.client.get("/control-access", headers={**headers, **extra})
        assert access.json() == {"commands_allowed": True, "reason": None, "role": "operator"}
        response = api.client.post(
            "/devices/node_01/commands", json={"action": "pump_off"}, headers={**headers, **extra},
        )
        # Past auth: the normal command path reports the (mocked) broker state.
        assert response.status_code == 503 and code(response) == "mqtt_unavailable"


def test_viewer_reads_but_gets_403_for_commands(api, monkeypatch):
    api.configure(operator_role="viewer")
    headers = api.login()
    assert api.client.get("/control-access", headers=headers).json() == {
        "commands_allowed": False, "reason": "forbidden", "role": "viewer",
    }
    monkeypatch.setattr(repository, "get_device_state", AsyncMock(return_value=None))
    assert api.client.get("/devices/node_01/state", headers=headers).status_code == 404  # read allowed
    api.bridge.is_connected.return_value = True
    for body in ({"action": "pump_on", "duration_seconds": 5}, {"action": "pump_off"}):
        response = api.client.post("/devices/node_01/commands", json=body, headers=headers)
        assert response.status_code == 403 and code(response) == "forbidden"
    api.bridge.publish.assert_not_called()


# --- rate limits ----------------------------------------------------------------------------


def test_sliding_window_limiter_with_fake_clock():
    now = [0.0]
    limiter = SlidingWindowLimiter(2, 10, clock=lambda: now[0])
    assert limiter.hit("k") is None and limiter.hit("k") is None
    assert limiter.hit("k") == 10
    now[0] = 4.0
    assert limiter.retry_after("k") == 6
    now[0] = 10.5
    assert limiter.hit("k") is None  # first event left the window
    assert limiter.hit("other") is None  # keys are independent
    limiter.reset("k")
    assert limiter.retry_after("k") is None


def test_login_failures_lock_with_429_and_retry_after(api):
    api.configure(login_max_failures=3, login_failure_window_seconds=120)
    for _ in range(3):
        assert api.client.post("/auth/login", json={"username": OPERATOR, "password": "nope nope"}).status_code == 401
    locked = api.client.post("/auth/login", json={"username": OPERATOR, "password": PASSWORD})
    assert locked.status_code == 429
    assert code(locked) == "login_rate_limited"
    assert 1 <= int(locked.headers["retry-after"]) <= 120
    assert locked.json()["detail"]["retry_after_seconds"] == int(locked.headers["retry-after"])
    assert "thử lại" in locked.json()["detail"]["message"]
    assert api.sessions.rows == {}


def test_unknown_usernames_share_one_bucket_and_success_resets(api):
    api.configure(login_max_failures=2)
    for name in ("a", "b"):
        api.client.post("/auth/login", json={"username": name, "password": "x"})
    assert api.client.post("/auth/login", json={"username": "c", "password": "x"}).status_code == 429
    # The real operator is not locked by failures on unknown names.
    api.login()
    api.client.post("/auth/login", json={"username": OPERATOR, "password": "bad one"})
    api.login()  # success resets the operator's failure count
    api.client.post("/auth/login", json={"username": OPERATOR, "password": "bad one"})
    api.login()


def test_chat_rate_limit_is_per_account_and_429(api, monkeypatch):
    api.configure(chat_rate_limit=2, chat_api_url="")
    headers = api.login()
    for _ in range(2):
        response = api.client.post("/chat", json={"message": "Xin chào"}, headers=headers)
        assert response.status_code == 503 and code(response) == "chat_unavailable"
    limited = api.client.post("/chat", json={"message": "Xin chào"}, headers=headers)
    assert limited.status_code == 429 and code(limited) == "chat_request_rate_limited"
    assert int(limited.headers["retry-after"]) >= 1


def test_chat_not_configured_is_clear_and_never_calls_upstream(api, monkeypatch):
    api.configure(chat_api_url="")
    upstream = AsyncMock()
    monkeypatch.setattr(app.state, "chat_client", upstream, raising=False)
    response = api.client.post("/chat", json={"message": "Xin chào"}, headers=api.login())
    detail = response.json()["detail"]
    assert response.status_code == 503
    assert detail["code"] == "chat_unavailable" and detail["reason"] == "not_configured"
    assert "CHAT_API_URL" in detail["message"] and "ngrok" not in detail["message"]
    upstream.post.assert_not_called()


def _fake_command_path(monkeypatch, api):
    """Let POST /commands run to completion without DB/MQTT."""
    now = datetime.now(timezone.utc)
    api.bridge.is_connected.return_value = True
    api.bridge.publish.return_value = True

    async def insert(_conn, command_id, device_id, sequence, action, params, boot, _timeout):
        return {
            "command_id": command_id, "device_id": device_id, "command_sequence": sequence,
            "action": action, "params": params, "target_boot_id": boot, "status": "pending",
            "device_ack": None, "reason": None, "created_at": now,
            "expires_at": now + timedelta(seconds=15), "published_at": None, "acked_at": None,
            "ack_boot_id": None, "state_confirmed_at": None, "confirmed_relay_state": None,
            "confirmed_state_sequence": None, "confirmed_boot_id": None, "finalized_at": None,
            "late_ack": None, "late_ack_at": None,
        }

    inserted = {}

    async def insert_and_keep(*args):
        inserted["row"] = await insert(*args)
        return inserted["row"]

    monkeypatch.setattr(repository, "current_boot_id", AsyncMock(return_value="boot_1"))
    monkeypatch.setattr(repository, "allocate_command_sequence", AsyncMock(return_value=1))
    monkeypatch.setattr(repository, "insert_command", insert_and_keep)
    monkeypatch.setattr(repository, "mark_published", AsyncMock(side_effect=lambda _c, _id: {**inserted["row"], "published_at": now}))


def test_pump_on_is_limited_per_device_but_pump_off_never(api, monkeypatch):
    api.configure(pump_on_rate_limit=2, pump_on_rate_window_seconds=60)
    _fake_command_path(monkeypatch, api)
    headers = api.login()
    on = {"action": "pump_on", "duration_seconds": 5}
    for _ in range(2):
        response = api.client.post("/devices/node_01/commands", json=on, headers=headers)
        assert response.status_code == 202 and response.json()["status"] == "pending"
    limited = api.client.post("/devices/node_01/commands", json=on, headers=headers)
    assert limited.status_code == 429 and code(limited) == "command_rate_limited"
    assert limited.headers["retry-after"]
    assert api.bridge.publish.call_count == 2  # the refused ON was never published
    # Emergency stop still goes out, repeatedly.
    for _ in range(5):
        off = api.client.post("/devices/node_01/commands", json={"action": "pump_off"}, headers=headers)
        assert off.status_code == 202
    # Another device has its own budget.
    assert api.client.post("/devices/node_02/commands", json=on, headers=headers).status_code == 202
