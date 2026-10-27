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
    chat_api_url: str = "https://sly-series-landowner.ngrok-free.dev/v1/chat/completions"
    chat_api_key: str | None = None
    chat_temperature: float = 0.7
    chat_max_tokens: int = 1024
    chat_timeout_seconds: int = 120

    @classmethod
    def from_env(cls) -> "Settings":
        temperature = float(os.getenv("CHAT_TEMPERATURE", "0.7"))
        if not math.isfinite(temperature) or not 0 <= temperature <= 2:
            raise ValueError("CHAT_TEMPERATURE must be between 0 and 2")
        chat_api_url = os.getenv("CHAT_API_URL", cls.chat_api_url).strip()
        if not chat_api_url.startswith(("https://", "http://")):
            raise ValueError("CHAT_API_URL must be an HTTP(S) endpoint")
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
