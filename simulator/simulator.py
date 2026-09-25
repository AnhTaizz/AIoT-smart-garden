"""Simulate one garden device over MQTT: telemetry plus the command loop.

All telemetry from this process is SIMULATED data. The payloads and the command
rules follow the v1 proposal in docs/INTERFACES.md, which is still DRAFT until
the team confirms it at G02.
"""

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

from device import DEFAULT_PUMP_MAX_SECONDS, DeviceRuntime, is_identifier, new_boot_id

LOGGER = logging.getLogger("smart-garden-simulator")
TOPIC_TEMPLATE = "garden/{device_id}/{kind}"
LOOP_TICK_SECONDS = 0.2


@dataclass(frozen=True)
class SimulatorConfig:
    broker: str
    port: int
    username: str | None
    password: str | None
    device_id: str
    boot_id: str
    interval_seconds: float
    message_count: int
    state_heartbeat_seconds: float
    pump_max_seconds: int
    clock_synced: bool
    sensor_error: str


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def parse_config(arguments: Sequence[str] | None = None) -> SimulatorConfig:
    parser = argparse.ArgumentParser(
        description=(
            "Mô phỏng một thiết bị vườn qua MQTT: telemetry, nhận command, "
            "gửi ACK và state. CLI ưu tiên hơn biến môi trường."
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
        "--device-id",
        default=os.getenv("DEVICE_ID", "node_01"),
        help="Mã thiết bị mô phỏng (env: DEVICE_ID; mặc định: node_01)",
    )
    parser.add_argument(
        "--boot-id",
        default=os.getenv("BOOT_ID"),
        help="boot_id cố định để kiểm thử (env: BOOT_ID; mặc định: sinh mới)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=os.getenv("TELEMETRY_INTERVAL_SECONDS", "2"),
        help=(
            "Số giây giữa hai telemetry "
            "(env: TELEMETRY_INTERVAL_SECONDS; mặc định: 2)"
        ),
    )
    parser.add_argument(
        "--count",
        type=int,
        default=os.getenv("TELEMETRY_MESSAGE_COUNT", "0"),
        help=(
            "Số telemetry rồi thoát; 0 chạy tới khi Ctrl+C "
            "(env: TELEMETRY_MESSAGE_COUNT; mặc định: 0)"
        ),
    )
    parser.add_argument(
        "--state-heartbeat",
        type=float,
        default=os.getenv("STATE_HEARTBEAT_SECONDS", "10"),
        help="Nhịp phát state (env: STATE_HEARTBEAT_SECONDS; mặc định: 10)",
    )
    parser.add_argument(
        "--pump-max-seconds",
        type=int,
        default=os.getenv("PUMP_MAX_SECONDS", str(DEFAULT_PUMP_MAX_SECONDS)),
        help=(
            "Giới hạn chạy bơm cục bộ của thiết bị "
            f"(env: PUMP_MAX_SECONDS; mặc định: {DEFAULT_PUMP_MAX_SECONDS})"
        ),
    )
    parser.add_argument(
        "--clock-unsynced",
        action="store_true",
        default=not _env_flag("CLOCK_SYNCED", True),
        help=(
            "Mô phỏng thiết bị chưa có giờ UTC đáng tin cậy: telemetry không có "
            "measured_at và pump_on bị từ chối bằng clock_unsynced"
        ),
    )
    parser.add_argument(
        "--sensor-error",
        choices=("none", "aht20", "soil", "both"),
        default=os.getenv("SENSOR_ERROR", "none"),
        help="Mô phỏng cảm biến lỗi: giá trị null kèm sensor_status error",
    )

    parsed = parser.parse_args(arguments)
    broker = parsed.broker.strip()
    device_id = parsed.device_id.strip()

    if not broker:
        parser.error("broker không được để trống")
    if not 1 <= parsed.port <= 65535:
        parser.error("port phải nằm trong khoảng 1..65535")
    if not is_identifier(device_id):
        parser.error("device_id chỉ gồm A-Z a-z 0-9 _ -, dài 1..64 ký tự")
    if parsed.interval <= 0:
        parser.error("interval phải lớn hơn 0")
    if parsed.count < 0:
        parser.error("count phải lớn hơn hoặc bằng 0")
    if parsed.state_heartbeat <= 0:
        parser.error("state-heartbeat phải lớn hơn 0")
    if parsed.pump_max_seconds < 1:
        parser.error("pump-max-seconds phải lớn hơn hoặc bằng 1")
    if parsed.password and not parsed.username:
        parser.error("cần username khi cấu hình password")

    boot_id = (parsed.boot_id or new_boot_id()).strip()
    if not is_identifier(boot_id):
        parser.error("boot_id chỉ gồm A-Z a-z 0-9 _ -, dài 1..64 ký tự")
    if parsed.sensor_error not in ("none", "aht20", "soil", "both"):
        parser.error("sensor-error phải là none, aht20, soil hoặc both")

    return SimulatorConfig(
        broker=broker,
        port=parsed.port,
        username=parsed.username,
        password=parsed.password,
        device_id=device_id,
        boot_id=boot_id,
        interval_seconds=parsed.interval,
        message_count=parsed.count,
        state_heartbeat_seconds=parsed.state_heartbeat,
        pump_max_seconds=parsed.pump_max_seconds,
        clock_synced=not parsed.clock_unsynced,
        sensor_error=parsed.sensor_error,
    )


def topic_for(device_id: str, kind: str) -> str:
    return TOPIC_TEMPLATE.format(device_id=device_id, kind=kind)


class Simulator:
    """Glue between the MQTT client and the pure device logic."""

    def __init__(self, config: SimulatorConfig, client: Any) -> None:
        self.config = config
        self.client = client
        self.runtime = DeviceRuntime(
            device_id=config.device_id,
            boot_id=config.boot_id,
            clock_synced=config.clock_synced,
            pump_max_seconds=config.pump_max_seconds,
        )
        self.lock = threading.Lock()
        self.connected = threading.Event()
        self.connection_error: list[str] = []
        self.started_at = time.monotonic()
        self.telemetry_sent = 0
        self.random_source = random.Random()

    # --- helpers -----------------------------------------------------------

    def _publish(
        self, kind: str, payload: dict[str, Any], qos: int, wait: bool = False
    ) -> None:
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        result = self.client.publish(
            topic_for(self.config.device_id, kind), encoded, qos=qos, retain=False
        )
        if not wait:
            # Never wait here: on_message runs on paho's network thread, and that
            # same thread has to send the packet, so waiting would stall the ACK
            # and state of every command until the timeout.
            return
        result.wait_for_publish(timeout=5)

    def _refresh_uptime(self) -> None:
        self.runtime.uptime_ms = int((time.monotonic() - self.started_at) * 1000)

    def publish_state(self, note: str, wait: bool = False) -> None:
        self._refresh_uptime()
        payload = self.runtime.state_payload()
        self._publish("state", payload, qos=1, wait=wait)
        LOGGER.info(
            "STATE %s relay_state=%s state_sequence=%d last_command_id=%s",
            note,
            payload["relay_state"],
            payload["state_sequence"],
            payload["last_command_id"],
        )

    def publish_telemetry(self) -> None:
        self._refresh_uptime()
        payload = self.runtime.telemetry_payload(
            self.random_source,
            aht20_ok=self.config.sensor_error not in ("aht20", "both"),
            soil_ok=self.config.sensor_error not in ("soil", "both"),
        )
        self._publish("telemetry", payload, qos=0)
        self.telemetry_sent += 1
        LOGGER.info(
            "ĐÃ GỬI TELEMETRY MÔ PHỎNG %d/%s sequence=%d clock_synced=%s",
            self.telemetry_sent,
            self.config.message_count or "∞",
            payload["sequence"],
            payload["clock_synced"],
        )

    # --- MQTT callbacks ----------------------------------------------------

    def on_connect(
        self, client: Any, _userdata: Any, _flags: Any, reason_code: Any, _props: Any
    ) -> None:
        if getattr(reason_code, "is_failure", reason_code != 0):
            self.connection_error.append(str(reason_code))
            self.connected.set()
            return
        client.subscribe(topic_for(self.config.device_id, "control"), qos=1)
        LOGGER.info(
            "Đã kết nối MQTT broker, subscribe %s",
            topic_for(self.config.device_id, "control"),
        )
        self.connected.set()
        with self.lock:
            # A device announces its state right after connecting, so the
            # backend learns the current boot_id before any pump_on.
            self.publish_state("sau khi kết nối")

    def on_message(self, _client: Any, _userdata: Any, message: Any) -> None:
        try:
            payload = json.loads(message.payload)
        except ValueError:
            LOGGER.warning("Bỏ qua command không đọc được JSON")
            return

        now = datetime.now(timezone.utc) if self.config.clock_synced else None
        with self.lock:
            decision = self.runtime.handle_command(payload, now, time.monotonic())
            if decision.status is None:
                LOGGER.info("Bỏ qua command không thuộc thiết bị này")
                return
            command_id = payload.get("command_id")
            self._publish(
                "ack", self.runtime.ack_payload(command_id, decision), qos=1
            )
            LOGGER.info(
                "ACK command_id=%s status=%s reason=%s duplicate=%s order_mark=%d",
                command_id,
                decision.status,
                decision.reason,
                decision.duplicate,
                self.runtime.order_mark,
            )
            if decision.status == "applied" and not decision.duplicate:
                self.publish_state("sau khi áp dụng command")

    # --- main loop ---------------------------------------------------------

    def run(self) -> int:
        config = self.config
        LOGGER.info(
            "Khởi động SIMULATOR broker=%s port=%d device_id=%s boot_id=%s "
            "interval=%.2fs count=%s heartbeat=%.1fs pump_max=%ds "
            "clock_synced=%s sensor_error=%s",
            config.broker,
            config.port,
            config.device_id,
            config.boot_id,
            config.interval_seconds,
            config.message_count or "liên tục",
            config.state_heartbeat_seconds,
            config.pump_max_seconds,
            config.clock_synced,
            config.sensor_error,
        )
        LOGGER.warning(
            "Toàn bộ telemetry của tiến trình này là DỮ LIỆU MÔ PHỎNG; "
            "contract telemetry-v1/command-v1 vẫn là DRAFT chờ G02."
        )

        self.client.connect(config.broker, config.port, keepalive=30)
        self.client.loop_start()
        try:
            if not self.connected.wait(timeout=10):
                raise TimeoutError("Hết thời gian chờ MQTT CONNACK")
            if self.connection_error:
                raise ConnectionError(
                    f"MQTT từ chối kết nối: {self.connection_error[0]}"
                )

            next_telemetry = time.monotonic()
            next_heartbeat = time.monotonic() + config.state_heartbeat_seconds
            while True:
                now = time.monotonic()
                with self.lock:
                    if self.runtime.pump_finished(now):
                        # The pump stopping by itself is reported as state; the
                        # command that started it stays applied in the backend.
                        self.publish_state("bơm tự tắt hết thời lượng")
                    if now >= next_telemetry:
                        self.publish_telemetry()
                        # Measured after publishing: a slow publish must not make
                        # the next tick fire immediately.
                        next_telemetry = time.monotonic() + config.interval_seconds
                    if now >= next_heartbeat:
                        self.publish_state("heartbeat")
                        next_heartbeat = (
                            time.monotonic() + config.state_heartbeat_seconds
                        )
                if config.message_count and self.telemetry_sent >= config.message_count:
                    LOGGER.info("Đã gửi đủ %d telemetry", config.message_count)
                    break
                time.sleep(LOOP_TICK_SECONDS)
        except KeyboardInterrupt:
            LOGGER.info("Đã nhận Ctrl+C, đang dừng simulator...")
        finally:
            with self.lock:
                if self.runtime.relay_state == "on":
                    # Losing the link must not leave the pump running.
                    self.runtime.relay_state = "off"
                    self.runtime.running_command_id = None
                    self.runtime.pump_stop_at = None
                    # Last message before exit: here it is worth waiting.
                    self.publish_state("tắt bơm trước khi thoát", wait=True)
            self.client.disconnect()
            self.client.loop_stop()
            LOGGER.info(
                "Simulator đã dừng gọn; telemetry đã gửi: %d", self.telemetry_sent
            )
        return self.telemetry_sent


def build_client(config: SimulatorConfig) -> Any:
    try:
        from paho.mqtt import client as mqtt
    except ModuleNotFoundError as error:
        raise RuntimeError(
            "Chưa cài paho-mqtt; chạy: python -m pip install -r requirements.txt"
        ) from error

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"smart-garden-simulator-{config.device_id}-{os.getpid()}",
        # Explicit clean session: the broker must not keep queued commands for
        # this device while it is offline.
        clean_session=True,
    )
    if config.username:
        client.username_pw_set(config.username, config.password)
    return client


def main(arguments: Sequence[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    config = parse_config(arguments)
    try:
        client = build_client(config)
        simulator = Simulator(config, client)
        client.on_connect = simulator.on_connect
        client.on_message = simulator.on_message
        simulator.run()
    except (ConnectionError, OSError, RuntimeError, TimeoutError) as error:
        LOGGER.error("Simulator thất bại: %s", error)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
