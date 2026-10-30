"""BC-02.1: parallel logins must not bypass limits or run unbounded scrypt.

The real scrypt (N=2^17, ~128 MiB) is replaced by a fake verifier that sleeps
in the worker thread and records how many run at once, so the tests check the
gatekeeping without burning CPU/RAM on hundreds of real hashes.
"""

import asyncio
import threading
import time

import httpx
import pytest

from app import auth
from app.main import app
from tests.conftest import OPERATOR, PASSWORD


class FakeVerifier:
    def __init__(self, delay=0.2):
        self.delay = delay
        self.calls = 0
        self.active = 0
        self.max_active = 0
        self._lock = threading.Lock()

    def __call__(self, password, encoded):
        with self._lock:
            self.calls += 1
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            time.sleep(self.delay)
            return password == PASSWORD
        finally:
            with self._lock:
                self.active -= 1


@pytest.fixture
def verifier(monkeypatch):
    fake = FakeVerifier()
    monkeypatch.setattr(auth, "verify_password", fake)
    return fake


def burst(payloads):
    """Send all login requests concurrently through the ASGI app."""

    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await asyncio.gather(
                *(client.post("/auth/login", json=payload) for payload in payloads)
            )

    return asyncio.run(run())


def codes(responses):
    return [r.json()["detail"]["code"] if r.status_code != 200 else "ok" for r in responses]


def test_parallel_wrong_logins_cannot_exceed_the_failure_limit(api, verifier):
    api.configure(login_max_failures=5, login_max_concurrent=20)
    responses = burst([{"username": OPERATOR, "password": "wrong-password"}] * 30)
    # Only `limit` attempts may ever reach the slow hash, however parallel.
    assert verifier.calls <= 5
    assert codes(responses).count("invalid_credentials") <= 5
    limited = [r for r in responses if r.status_code == 429]
    assert len(limited) >= 25
    assert all(r.headers.get("retry-after") for r in limited)
    # The account stays locked afterwards, also for the right password.
    locked = api.client.post("/auth/login", json={"username": OPERATOR, "password": PASSWORD})
    assert locked.status_code == 429 and locked.json()["detail"]["code"] == "login_rate_limited"


def test_concurrent_hashes_are_capped_and_excess_is_rejected_not_queued(api, verifier):
    # High failure budget so only the concurrency cap applies.
    api.configure(login_max_failures=1000, login_max_concurrent=2)
    started = time.monotonic()
    responses = burst([{"username": f"user{i}", "password": "x"} for i in range(12)])
    elapsed = time.monotonic() - started
    assert verifier.max_active <= 2
    assert verifier.calls <= 2
    busy = [r for r in responses if r.status_code == 429]
    assert len(busy) >= 10
    assert {r.json()["detail"]["code"] for r in busy} == {"login_busy"}
    assert all(int(r.headers["retry-after"]) >= 1 for r in busy)
    assert all("message" in r.json()["detail"] for r in busy)
    # Rejected requests do not wait behind the hashing ones.
    assert elapsed < 12 * verifier.delay


def test_valid_login_succeeds_when_not_limited_and_after_a_busy_burst(api, verifier):
    api.configure(login_max_failures=1000, login_max_concurrent=1)
    burst([{"username": f"user{i}", "password": "x"} for i in range(5)])
    response = api.client.post("/auth/login", json={"username": OPERATOR, "password": PASSWORD})
    assert response.status_code == 200
    assert verifier.active == 0


def test_cap_is_released_even_if_the_client_disconnects(api, verifier):
    """A cancelled request keeps its slot until its hash thread really ends."""
    api.configure(login_max_failures=1000, login_max_concurrent=1)
    verifier.delay = 0.4

    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            first = asyncio.create_task(
                client.post("/auth/login", json={"username": OPERATOR, "password": "wrong-password"})
            )
            await asyncio.sleep(0.1)
            first.cancel()  # the client goes away while the hash still runs
            await asyncio.sleep(0.05)
            during = await client.post("/auth/login", json={"username": OPERATOR, "password": PASSWORD})
            await asyncio.sleep(0.5)
            after = await client.post("/auth/login", json={"username": OPERATOR, "password": PASSWORD})
            return during, after

    during, after = asyncio.run(run())
    assert during.status_code == 429 and during.json()["detail"]["code"] == "login_busy"
    assert after.status_code == 200
    assert verifier.max_active == 1


def test_production_scrypt_cost_is_unchanged():
    assert auth.DEFAULT_LOG2_N == 17
    assert auth.parse_password_hash(auth.hash_password("x" * 12))[0] == 17
