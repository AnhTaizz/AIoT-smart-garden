"""Publish clearly labelled bootstrap telemetry to an MQTT broker."""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Sequence

LOGGER = logging.getLogger("smart-garden-simulator")
DEFAULT_TOPIC_TEMPLATE = "garden/{device_id}/telemetry"
SCHEMA_NAME = "bootstrap-telemetry-v0"


@dataclass(frozen=True)
class SimulatorConfig:
    broker: str
    port: int
    username: str | None
    password: str | None
    topic: str
    device_id: str
    interval_seconds: float
    message_count: int


def build_payload(
    device_id: str,
    sequence: int,
    random_source: random.Random,
) -> dict[str, object]:
    """Create one proposed bootstrap payload containing simulated values."""
    measured_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    return {
        "schema": SCHEMA_NAME,
        "simulated": True,
        "device_id": device_id,
        "sequence": sequence,
        "measured_at": measured_at.replace("+00:00", "Z"),
        "temperature_c": round(random_source.uniform(24.0, 32.0), 2),
        "air_humidity_pct": round(random_source.uniform(55.0, 85.0), 2),
        "soil_moisture_pct": round(random_source.uniform(30.0, 70.0), 2),
    }


def parse_config(arguments: Sequence[str] | None = None) -> SimulatorConfig:
    parser = argparse.ArgumentParser(
        description=(
            "Phát telemetry mô phỏng lên Mosquitto. "
            "CLI ưu tiên hơn biến môi trường."
        )
    )
    parser.add_argument(
        "--broker",
        default=os.getenv("MQTT_BROKER_HOST", "127.0.0.1"),
        help="MQTT broker (env: MQTT_BROKER_HOST; mặc định: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=os.getenv("MQTT_BROKER_PORT", "1883"),
        help="MQTT port (env: MQTT_BROKER_PORT; mặc định: 1883)",
    )
    parser.add_argument(
        "--username",
        default=os.getenv("MQTT_USERNAME"),
        help="MQTT username nếu broker yêu cầu (env: MQTT_USERNAME)",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("MQTT_PASSWORD"),
        help="MQTT password nếu broker yêu cầu (env: MQTT_PASSWORD)",
    )
    parser.add_argument(
        "--topic",
        default=os.getenv("MQTT_TOPIC"),
        help=(
            "Topic publish (env: MQTT_TOPIC; "
            "mặc định: garden/<device_id>/telemetry)"
        ),
    )
    parser.add_argument(
        "--device-id",
        default=os.getenv("DEVICE_ID", "node_01"),
        help="Mã thiết bị mô phỏng (env: DEVICE_ID; mặc định: node_01)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=os.getenv("TELEMETRY_INTERVAL_SECONDS", "2"),
        help=(
            "Số giây giữa hai bản tin "
            "(env: TELEMETRY_INTERVAL_SECONDS; mặc định: 2)"
        ),
    )
    parser.add_argument(
        "--count",
        type=int,
        default=os.getenv("TELEMETRY_MESSAGE_COUNT", "0"),
        help=(
            "Số bản tin; 0 gửi liên tục tới khi Ctrl+C "
            "(env: TELEMETRY_MESSAGE_COUNT; mặc định: 0)"
        ),
    )

    parsed = parser.parse_args(arguments)
    broker = parsed.broker.strip()
    device_id = parsed.device_id.strip()
    topic = (parsed.topic or DEFAULT_TOPIC_TEMPLATE.format(device_id=device_id)).strip()

    if not broker:
        parser.error("broker không được để trống")
    if not 1 <= parsed.port <= 65535:
        parser.error("port phải nằm trong khoảng 1..65535")
    if not device_id:
        parser.error("device_id không được để trống")
    if not topic:
        parser.error("topic không được để trống")
    if "+" in topic or "#" in topic:
        parser.error("topic publish không được chứa wildcard + hoặc #")
    if parsed.interval <= 0:
        parser.error("interval phải lớn hơn 0")
    if parsed.count < 0:
        parser.error("count phải lớn hơn hoặc bằng 0")
    if parsed.password and not parsed.username:
        parser.error("cần username khi cấu hình password")

    return SimulatorConfig(
        broker=broker,
        port=parsed.port,
        username=parsed.username,
        password=parsed.password,
        topic=topic,
        device_id=device_id,
        interval_seconds=parsed.interval,
        message_count=parsed.count,
    )


def publish_telemetry(config: SimulatorConfig) -> int:
    try:
        from paho.mqtt import client as mqtt
    except ModuleNotFoundError as error:
        raise RuntimeError(
            "Chưa cài paho-mqtt; chạy: python -m pip install -r requirements.txt"
        ) from error

    connected = threading.Event()
    connection_error: list[str] = []
    random_source = random.Random()
    client_id = f"smart-garden-simulator-{config.device_id}-{os.getpid()}"
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)

    def on_connect(
        _client: Any,
        _userdata: Any,
        _flags: Any,
        reason_code: Any,
        _properties: Any,
    ) -> None:
        if reason_code == 0:
            LOGGER.info("Đã kết nối MQTT broker")
        else:
            connection_error.append(str(reason_code))
        connected.set()

    client.on_connect = on_connect
    if config.username:
        client.username_pw_set(config.username, config.password)

    LOGGER.info(
        "Khởi động SIMULATOR broker=%s port=%d topic=%s device_id=%s "
        "interval=%.2fs count=%s authentication=%s",
        config.broker,
        config.port,
        config.topic,
        config.device_id,
        config.interval_seconds,
        config.message_count if config.message_count else "liên tục",
        "có" if config.username else "không",
    )
    LOGGER.warning(
        "Toàn bộ telemetry của tiến trình này là DỮ LIỆU MÔ PHỎNG; "
        "schema %s chỉ là đề xuất bootstrap chưa được G02 chốt.",
        SCHEMA_NAME,
    )

    loop_started = False
    sent_count = 0
    try:
        client.connect(config.broker, config.port, keepalive=60)
        client.loop_start()
        loop_started = True

        if not connected.wait(timeout=10):
            raise TimeoutError("Hết thời gian chờ MQTT CONNACK")
        if connection_error:
            raise ConnectionError(f"MQTT từ chối kết nối: {connection_error[0]}")

        while config.message_count == 0 or sent_count < config.message_count:
            sequence = sent_count + 1
            payload = build_payload(config.device_id, sequence, random_source)
            encoded_payload = json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            publish_result = client.publish(
                config.topic,
                encoded_payload,
                qos=0,
                retain=False,
            )
            if publish_result.rc != mqtt.MQTT_ERR_SUCCESS:
                raise ConnectionError(
                    f"Không thể publish MQTT, result code={publish_result.rc}"
                )
            publish_result.wait_for_publish(timeout=5)
            sent_count = sequence
            expected = config.message_count if config.message_count else "∞"
            LOGGER.info(
                "ĐÃ GỬI DỮ LIỆU MÔ PHỎNG %d/%s topic=%s payload=%s",
                sent_count,
                expected,
                config.topic,
                encoded_payload,
            )

            if config.message_count == 0 or sent_count < config.message_count:
                time.sleep(config.interval_seconds)
    except KeyboardInterrupt:
        LOGGER.info("Đã nhận Ctrl+C, đang dừng simulator...")
    finally:
        if loop_started:
            client.disconnect()
            client.loop_stop()
        LOGGER.info("Simulator đã dừng gọn; tổng số bản tin đã gửi: %d", sent_count)

    return sent_count


def main(arguments: Sequence[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    config = parse_config(arguments)
    try:
        publish_telemetry(config)
    except (ConnectionError, OSError, RuntimeError, TimeoutError) as error:
        LOGGER.error("Simulator thất bại: %s", error)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

