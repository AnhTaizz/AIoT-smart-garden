"""Operator authentication for the demo (BC-02).

- One operator account from the environment (`OPERATOR_USERNAME`,
  `OPERATOR_PASSWORD_HASH`, `OPERATOR_ROLE`). No password or secret lives in the
  repository or the app; without valid configuration login fails closed.
- Passwords are checked against a scrypt hash (memory-hard, Python standard
  library, no extra dependency). Format: `scrypt:<log2 N>:<r>:<p>:<salt>:<hash>`
  with URL-safe base64, no `$` so Compose does not try to interpolate it.
- A login creates an opaque random bearer token. PostgreSQL stores only its
  SHA-256, the expiry and the revocation time, so logout and expiry are
  enforced server-side. Changing the configured account invalidates sessions.
- Passwords and tokens are never logged.

Generate a hash (prompts twice, prints only the hash):
    python -m app.auth hash-password
"""

import asyncio
import base64
import getpass
import hashlib
import hmac
import logging
import secrets
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from . import repository
from .config import Settings
from .ratelimit import SlidingWindowLimiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth")

DEFAULT_LOG2_N = 17  # OWASP scrypt baseline: N=2^17, r=8, p=1 (128 MiB)
MIN_LOG2_N = 14
MAX_LOG2_N = 20
MIN_PASSWORD_LENGTH = 10
MAX_TOKEN_LENGTH = 256
UNKNOWN_USER_KEY = "*"
BEARER = {"WWW-Authenticate": "Bearer"}

AUTH_ERRORS = {
    "auth_required": "Cần đăng nhập để dùng chức năng này.",
    "invalid_session": "Phiên đăng nhập không hợp lệ, đã hết hạn hoặc đã đăng xuất. Vui lòng đăng nhập lại.",
    "invalid_credentials": "Tên đăng nhập hoặc mật khẩu không đúng.",
    "auth_not_configured": "Backend chưa cấu hình tài khoản vận hành nên không thể đăng nhập.",
    "forbidden": "Tài khoản này không có quyền thực hiện thao tác này.",
    "login_rate_limited": "Đăng nhập sai quá nhiều lần. Vui lòng thử lại sau.",
    "login_busy": "Máy chủ đang xử lý quá nhiều lượt đăng nhập. Vui lòng thử lại sau vài giây.",
    "chat_request_rate_limited": "Bạn gửi câu hỏi quá nhanh. Vui lòng chờ rồi thử lại.",
    "command_rate_limited": "Lệnh bật bơm được gửi quá dày. Vui lòng chờ rồi thử lại; lệnh tắt bơm không bị giới hạn này.",
}


# --- password hashing -----------------------------------------------------------


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _scrypt(password: str, salt: bytes, log2_n: int, r: int, p: int) -> bytes:
    n = 1 << log2_n
    return hashlib.scrypt(
        password.encode(), salt=salt, n=n, r=r, p=p,
        maxmem=2 * 128 * r * n * p + 32 * 1024 * 1024, dklen=32,
    )


def hash_password(password: str, log2_n: int = DEFAULT_LOG2_N) -> str:
    if not MIN_LOG2_N <= log2_n <= MAX_LOG2_N:
        raise ValueError("unsupported scrypt cost")
    salt = secrets.token_bytes(16)
    digest = _scrypt(password, salt, log2_n, 8, 1)
    return f"scrypt:{log2_n}:8:1:{_b64(salt)}:{_b64(digest)}"


def parse_password_hash(encoded: str) -> tuple[int, int, int, bytes, bytes] | None:
    """Return (log2 N, r, p, salt, digest) or None for an unusable hash."""
    parts = encoded.split(":")
    if len(parts) != 6 or parts[0] != "scrypt":
        return None
    try:
        log2_n, r, p = int(parts[1]), int(parts[2]), int(parts[3])
        salt, digest = _unb64(parts[4]), _unb64(parts[5])
    except ValueError:
        return None
    if not (MIN_LOG2_N <= log2_n <= MAX_LOG2_N and 1 <= r <= 32 and 1 <= p <= 4):
        return None
    if len(salt) < 16 or len(digest) != 32:
        return None
    return log2_n, r, p, salt, digest


def verify_password(password: str, encoded: str) -> bool:
    parsed = parse_password_hash(encoded)
    if parsed is None:
        return False
    log2_n, r, p, salt, digest = parsed
    return hmac.compare_digest(_scrypt(password, salt, log2_n, r, p), digest)


def credential_id(settings: Settings) -> str | None:
    """Fingerprint of the configured account, or None when it is unusable."""
    if not settings.operator_username or parse_password_hash(settings.operator_password_hash) is None:
        return None
    material = "\0".join(
        (settings.operator_username, settings.operator_password_hash, settings.operator_role)
    )
    return hashlib.sha256(material.encode()).hexdigest()[:32]


def token_hash(token: str) -> bytes:
    # The token has 256 random bits, so a fast hash is enough to keep the
    # stored value useless to someone who reads the table.
    return hashlib.sha256(token.encode()).digest()


# --- rate limits ------------------------------------------------------------------


LOGIN_BUSY_RETRY_SECONDS = 2


@dataclass
class Limiters:
    login_failures: SlidingWindowLimiter
    chat: SlidingWindowLimiter
    pump_on: SlidingWindowLimiter
    login_max_concurrent: int = 2
    # Password checks currently running in worker threads (this process only).
    verifying: int = 0


def limiters(request: Request) -> Limiters:
    state = request.app.state
    if getattr(state, "limiters", None) is None:
        settings: Settings = state.settings
        state.limiters = Limiters(
            login_failures=SlidingWindowLimiter(
                settings.login_max_failures, settings.login_failure_window_seconds
            ),
            chat=SlidingWindowLimiter(settings.chat_rate_limit, settings.chat_rate_window_seconds),
            pump_on=SlidingWindowLimiter(
                settings.pump_on_rate_limit, settings.pump_on_rate_window_seconds
            ),
            login_max_concurrent=settings.login_max_concurrent,
        )
    return state.limiters


def rate_limited(code: str, retry_after: int) -> HTTPException:
    return HTTPException(
        status_code=429,
        detail={"code": code, "retry_after_seconds": retry_after},
        headers={"Retry-After": str(retry_after)},
    )


# --- sessions -----------------------------------------------------------------------


@dataclass(frozen=True)
class Session:
    username: str
    role: Literal["operator", "viewer"]
    expires_at: datetime
    token_hash: bytes


def _bearer_token(request: Request) -> str | None:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token or len(token) > MAX_TOKEN_LENGTH:
        return None
    return token


async def require_session(request: Request) -> Session:
    """401 unless the request carries a live, unrevoked session token."""
    token = _bearer_token(request)
    if token is None:
        raise HTTPException(401, "auth_required", headers=BEARER)
    current = credential_id(request.app.state.settings)
    if current is None:
        raise HTTPException(401, "invalid_session", headers=BEARER)
    hashed = token_hash(token)
    async with request.app.state.pool.connection() as conn:
        row = await repository.get_active_session(conn, hashed, current)
    if row is None:
        raise HTTPException(401, "invalid_session", headers=BEARER)
    return Session(row["username"], row["role"], row["expires_at"], hashed)


async def require_operator(session: Annotated[Session, Depends(require_session)]) -> Session:
    """403 for an authenticated account that may only read (viewer)."""
    if session.role != "operator":
        raise HTTPException(403, "forbidden")
    return session


SessionDep = Annotated[Session, Depends(require_session)]
OperatorDep = Annotated[Session, Depends(require_operator)]


# --- endpoints ----------------------------------------------------------------------


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class UserOut(BaseModel):
    username: str
    role: Literal["operator", "viewer"]


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime
    user: UserOut


class MeResponse(BaseModel):
    user: UserOut
    expires_at: datetime


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, request: Request) -> LoginResponse:
    settings: Settings = request.app.state.settings
    current = credential_id(settings)
    if current is None:
        logger.warning("Login refused: operator account is not configured")
        raise HTTPException(503, "auth_not_configured")
    known_user = hmac.compare_digest(body.username, settings.operator_username)
    key = settings.operator_username if known_user else UNKNOWN_USER_KEY
    gate = limiters(request)
    failures = gate.login_failures
    # Everything up to the first await runs without yielding to the event loop,
    # so the checks and reservations below are atomic for this process.
    wait = failures.retry_after(key)
    if wait is not None:
        raise rate_limited("login_rate_limited", wait)
    if gate.verifying >= gate.login_max_concurrent:
        # Reject instead of queueing: a burst cannot pile up pending hashes.
        raise rate_limited("login_busy", LOGIN_BUSY_RETRY_SECONDS)
    # Count this attempt as a failure *before* hashing, so parallel requests
    # cannot all pass the check above; a success removes it again below.
    failures.record(key)
    gate.verifying += 1

    def release(_job: asyncio.Future) -> None:
        gate.verifying -= 1

    # Always run the slow hash so an unknown username costs the same time.
    job = asyncio.ensure_future(
        asyncio.to_thread(verify_password, body.password, settings.operator_password_hash)
    )
    # The slot is freed when the thread really finishes, even if the client
    # disconnects and this request is cancelled (shield keeps the job alive).
    job.add_done_callback(release)
    password_ok = await asyncio.shield(job)
    if not (known_user and password_ok):
        logger.info("Login failed")
        raise HTTPException(401, "invalid_credentials")
    failures.reset(key)
    token = secrets.token_urlsafe(32)
    async with request.app.state.pool.connection() as conn:
        row = await repository.create_session(
            conn, token_hash(token), settings.operator_username, settings.operator_role,
            current, settings.auth_session_ttl_seconds,
        )
    logger.info("Login succeeded role=%s", settings.operator_role)
    return LoginResponse(
        access_token=token, expires_at=row["expires_at"],
        user=UserOut(username=row["username"], role=row["role"]),
    )


@router.get("/me", response_model=MeResponse)
async def me(session: SessionDep) -> MeResponse:
    return MeResponse(
        user=UserOut(username=session.username, role=session.role),
        expires_at=session.expires_at,
    )


@router.post("/logout")
async def logout(session: SessionDep, request: Request) -> dict[str, str]:
    async with request.app.state.pool.connection() as conn:
        await repository.revoke_session(conn, session.token_hash)
    return {"status": "logged_out"}


def _cli(argv: list[str]) -> int:
    if argv[1:] != ["hash-password"]:
        print("Usage: python -m app.auth hash-password", file=sys.stderr)
        return 2
    password = getpass.getpass("Mật khẩu operator: ")
    if len(password) < MIN_PASSWORD_LENGTH:
        print(f"Mật khẩu cần ít nhất {MIN_PASSWORD_LENGTH} ký tự.", file=sys.stderr)
        return 1
    if getpass.getpass("Nhập lại: ") != password:
        print("Hai lần nhập không khớp.", file=sys.stderr)
        return 1
    print(hash_password(password))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli(sys.argv))
