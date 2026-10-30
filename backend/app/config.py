import os
import math
from dataclasses import dataclass
from typing import Any


def _int_env(name: str, default: int, minimum: int = 1) -> int:
    value = int(os.getenv(name, str(default)))
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


@dataclass(frozen=True)
class Settings:
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    db_connect_timeout_seconds: int
    mqtt_host: str
    mqtt_port: int
    mqtt_username: str | None
    mqtt_password: str | None
    mqtt_client_id: str
    command_timeout_seconds: int
    command_max_duration_seconds: int
    telemetry_stale_seconds: int
    # Empty means "not configured": /chat answers chat_unavailable.
    chat_api_url: str = ""
    chat_api_key: str | None = None
    chat_temperature: float = 0.7
    chat_max_tokens: int = 1024
    chat_timeout_seconds: int = 120
    cors_origins: tuple[str, ...] = ()
    # One operator account; no credentials means authentication fails closed.
    operator_username: str = ""
    operator_password_hash: str = ""
    operator_role: str = "operator"
    auth_session_ttl_seconds: int = 8 * 3600
    login_max_failures: int = 5
    login_failure_window_seconds: int = 300
    chat_rate_limit: int = 5
    chat_rate_window_seconds: int = 60
    pump_on_rate_limit: int = 6
    pump_on_rate_window_seconds: int = 60

    @classmethod
    def from_env(cls) -> "Settings":
        temperature = float(os.getenv("CHAT_TEMPERATURE", "0.7"))
        if not math.isfinite(temperature) or not 0 <= temperature <= 2:
            raise ValueError("CHAT_TEMPERATURE must be between 0 and 2")
        chat_api_url = os.getenv("CHAT_API_URL", "").strip()
        if chat_api_url and not chat_api_url.startswith(("https://", "http://")):
            raise ValueError("CHAT_API_URL must be an HTTP(S) endpoint")
        operator_role = os.getenv("OPERATOR_ROLE", "operator").strip()
        if operator_role not in ("operator", "viewer"):
            raise ValueError("OPERATOR_ROLE must be 'operator' or 'viewer'")
        return cls(
            db_host=os.getenv("DB_HOST", "postgres"),
            db_port=_int_env("DB_PORT", 5432),
            db_name=os.getenv("DB_NAME", "smart_garden"),
            db_user=os.getenv("DB_USER", "smart_garden"),
            db_password=os.getenv("DB_PASSWORD", ""),
            db_connect_timeout_seconds=_int_env("DB_CONNECT_TIMEOUT_SECONDS", 2),
            mqtt_host=os.getenv("MQTT_HOST", "mosquitto"),
            mqtt_port=_int_env("MQTT_PORT", 1883),
            mqtt_username=os.getenv("MQTT_USERNAME") or None,
            mqtt_password=os.getenv("MQTT_PASSWORD") or None,
            mqtt_client_id=os.getenv("MQTT_CLIENT_ID", "smart-garden-backend"),
            command_timeout_seconds=_int_env("COMMAND_TIMEOUT_SECONDS", 15),
            command_max_duration_seconds=_int_env(
                "COMMAND_MAX_DURATION_SECONDS", 120
            ),
            telemetry_stale_seconds=_int_env("TELEMETRY_STALE_SECONDS", 30),
            chat_api_url=chat_api_url,
            chat_api_key=os.getenv("CHAT_API_KEY") or None,
            chat_temperature=temperature,
            chat_max_tokens=_int_env("CHAT_MAX_TOKENS", 1024),
            chat_timeout_seconds=_int_env("CHAT_TIMEOUT_SECONDS", 120),
            operator_username=os.getenv("OPERATOR_USERNAME", "").strip(),
            operator_password_hash=os.getenv("OPERATOR_PASSWORD_HASH", "").strip(),
            operator_role=operator_role,
            auth_session_ttl_seconds=_int_env("AUTH_SESSION_TTL_SECONDS", 8 * 3600, minimum=60),
            login_max_failures=_int_env("LOGIN_MAX_FAILURES", 5),
            login_failure_window_seconds=_int_env("LOGIN_FAILURE_WINDOW_SECONDS", 300),
            chat_rate_limit=_int_env("CHAT_RATE_LIMIT", 5),
            chat_rate_window_seconds=_int_env("CHAT_RATE_WINDOW_SECONDS", 60),
            pump_on_rate_limit=_int_env("PUMP_ON_RATE_LIMIT", 6),
            pump_on_rate_window_seconds=_int_env("PUMP_ON_RATE_WINDOW_SECONDS", 60),
            cors_origins=tuple(
                origin.strip().rstrip("/")
                for origin in os.getenv(
                    "CORS_ORIGINS",
                    "http://localhost:5173,http://127.0.0.1:5173,"
                    "https://localhost,capacitor://localhost",
                ).split(",")
                if origin.strip()
            ),
        )

    def database_connection_parameters(self) -> dict[str, Any]:
        """Build connection parameters without placing credentials in a URL."""
        return {
            "host": self.db_host,
            "port": self.db_port,
            "dbname": self.db_name,
            "user": self.db_user,
            "password": self.db_password,
            "connect_timeout": self.db_connect_timeout_seconds,
        }
