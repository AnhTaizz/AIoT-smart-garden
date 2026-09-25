"""Thread-safe bridge between paho-mqtt's network thread and asyncio."""

import asyncio
import logging
import os
from typing import Any

from paho.mqtt import client as mqtt

from .config import Settings

logger = logging.getLogger(__name__)

SUBSCRIPTIONS = [
    ("garden/+/telemetry", 0),
    ("garden/+/ack", 1),
    ("garden/+/state", 1),
]
QUEUE_SIZE = 1000


class MqttBridge:
    def __init__(
        self,
        settings: Settings,
        loop: asyncio.AbstractEventLoop,
        queue: "asyncio.Queue[tuple[str, bytes]]",
    ) -> None:
        self._settings = settings
        self._loop = loop
        self._queue = queue
        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"{settings.mqtt_client_id}-{os.getpid()}",
        )
        if settings.mqtt_username:
            self._client.username_pw_set(
                settings.mqtt_username, settings.mqtt_password
            )
        self._client.reconnect_delay_set(min_delay=1, max_delay=30)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

    def start(self) -> None:
        # connect_async + loop_start keeps retrying if the broker is not up yet.
        self._client.connect_async(
            self._settings.mqtt_host, self._settings.mqtt_port, keepalive=30
        )
        self._client.loop_start()

    def stop(self) -> None:
        self._client.disconnect()
        self._client.loop_stop()

    def is_connected(self) -> bool:
        return self._client.is_connected()

    def publish(self, topic: str, payload: str, qos: int = 1) -> bool:
        # Commands are never retained: a reconnecting device must not replay them.
        info = self._client.publish(topic, payload, qos=qos, retain=False)
        return info.rc == mqtt.MQTT_ERR_SUCCESS

    def _on_connect(
        self, client: Any, _userdata: Any, _flags: Any, reason_code: Any, _props: Any
    ) -> None:
        if reason_code.is_failure:
            logger.warning("MQTT connection refused: %s", reason_code)
            return
        client.subscribe(SUBSCRIPTIONS)
        logger.info(
            "MQTT connected; subscribed to %s", [topic for topic, _ in SUBSCRIPTIONS]
        )

    def _on_disconnect(
        self, _client: Any, _userdata: Any, _flags: Any, reason_code: Any, _props: Any
    ) -> None:
        logger.warning("MQTT disconnected: %s", reason_code)

    def _on_message(self, _client: Any, _userdata: Any, message: Any) -> None:
        # Runs on paho's thread: hand the message to the event loop untouched.
        self._loop.call_soon_threadsafe(
            self._enqueue, message.topic, bytes(message.payload)
        )

    def _enqueue(self, topic: str, payload: bytes) -> None:
        try:
            self._queue.put_nowait((topic, payload))
        except asyncio.QueueFull:
            logger.warning("MQTT queue full; dropped message topic=%s", topic)
