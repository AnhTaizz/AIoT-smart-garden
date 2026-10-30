"""Run real local Compose integration tests without printing .env credentials.

From the repository root:
    .venv/Scripts/python.exe backend/tests/run_e2e.py
    .venv/Scripts/python.exe backend/tests/run_e2e.py --live-chat
Extra pytest options (e.g. -k deadline) are forwarded.
"""

import argparse
import asyncio
import os
from pathlib import Path
import sys

from dotenv import dotenv_values
import pytest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live-chat", action="store_true", help="Run opt-in chat tests through Nginx; makes real Kaggle calls")
    options, extra = parser.parse_known_args()
    root = Path(__file__).resolve().parents[2]
    values = dotenv_values(root / ".env")
    if not all(values.get(key) for key in ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD")):
        parser.error("Cần .env với cấu hình PostgreSQL của stack local đang chạy.")
    defaults = {
        "E2E_API_BASE_URL": "http://127.0.0.1:" + values.get("API_PORT", "8000"),
        "E2E_MQTT_HOST": "127.0.0.1",
        "E2E_MQTT_PORT": values.get("MQTT_PORT", "1883"),
        "E2E_CHAT_PROXY_URL": "http://127.0.0.1:" + values.get("FRONTEND_PORT", "5173") + "/api",
        "E2E_PROXY_URL": "http://127.0.0.1:" + values.get("FRONTEND_PORT", "5173") + "/api",
        "DB_HOST": "127.0.0.1", "DB_PORT": values.get("POSTGRES_PORT", "5432"),
        "DB_NAME": values["POSTGRES_DB"], "DB_USER": values["POSTGRES_USER"], "DB_PASSWORD": values["POSTGRES_PASSWORD"],
    }
    for key, value in defaults.items():
        os.environ.setdefault(key, value)
    if sys.platform == "win32":
        # psycopg async connections do not support the default Proactor loop.
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    os.chdir(root / "backend")
    sys.path.insert(0, str(root / "backend"))
    if options.live_chat:
        os.environ["E2E_CHAT_LIVE"] = "1"
        selection = ["tests/e2e/test_chat_e2e.py"]
    else:
        selection = ["tests/e2e", "--ignore=tests/e2e/test_chat_e2e.py"]
    return pytest.main(["-q", *selection, *extra])


if __name__ == "__main__":
    raise SystemExit(main())
