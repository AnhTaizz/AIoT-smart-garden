import json
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from simulator import Simulator, SimulatorConfig, main, parse_config, topic_for


class FakePublishResult:
    def wait_for_publish(self, timeout):
        raise AssertionError("callback safety path must not wait for MQTT publish")


class FakeClient:
    def __init__(self):
        self.published = []
        self.subscriptions = []
        self.on_connect = None
        self.on_disconnect = None
        self.on_message = None

    def subscribe(self, topic, qos):
        self.subscriptions.append((topic, qos))

    def publish(self, topic, payload, qos, retain):
        self.published.append((topic, json.loads(payload), qos, retain))
        return FakePublishResult()


def simulator_config():
    return SimulatorConfig(
        broker="broker",
        port=1883,
        username=None,
        password=None,
        device_id="node_callback",
        boot_id="boot_callback",
        interval_seconds=2,
        message_count=0,
        state_heartbeat_seconds=10,
        pump_max_seconds=60,
        clock_synced=True,
        sensor_error="none",
    )


def pump_on_message(simulator):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        payload=json.dumps(
            {
                "schema": "command-v1",
                "command_id": str(uuid.uuid4()),
                "device_id": simulator.config.device_id,
                "command_sequence": 1,
                "action": "pump_on",
                "params": {"duration_seconds": 30},
                "target_boot_id": simulator.runtime.boot_id,
                "issued_at": now.isoformat(),
                "expires_at": (now + timedelta(seconds=15)).isoformat(),
            }
        ).encode()
    )


class TopicTests(unittest.TestCase):
    def test_all_four_topics_derive_from_the_device_id(self):
        self.assertEqual(
            topic_for("node_01", "telemetry"), "garden/node_01/telemetry"
        )
        self.assertEqual(topic_for("node_01", "control"), "garden/node_01/control")
        self.assertEqual(topic_for("node_01", "ack"), "garden/node_01/ack")
        self.assertEqual(topic_for("node_01", "state"), "garden/node_01/state")


class ConfigTests(unittest.TestCase):
    @patch.dict(
        "os.environ",
        {
            "MQTT_BROKER_HOST": "broker.example",
            "MQTT_BROKER_PORT": "2883",
            "DEVICE_ID": "node_env",
            "BOOT_ID": "boot_env1234",
            "TELEMETRY_INTERVAL_SECONDS": "3.5",
            "TELEMETRY_MESSAGE_COUNT": "4",
            "STATE_HEARTBEAT_SECONDS": "7",
            "PUMP_MAX_SECONDS": "45",
        },
        clear=True,
    )
    def test_environment_configuration(self):
        config = parse_config([])

        self.assertEqual(config.broker, "broker.example")
        self.assertEqual(config.port, 2883)
        self.assertEqual(config.device_id, "node_env")
        self.assertEqual(config.boot_id, "boot_env1234")
        self.assertEqual(config.interval_seconds, 3.5)
        self.assertEqual(config.message_count, 4)
        self.assertEqual(config.state_heartbeat_seconds, 7)
        self.assertEqual(config.pump_max_seconds, 45)
        self.assertTrue(config.clock_synced)
        self.assertEqual(config.sensor_error, "none")

    def test_cli_takes_priority_over_environment(self):
        with patch.dict("os.environ", {"DEVICE_ID": "node_env"}, clear=True):
            config = parse_config(
                ["--device-id", "node_cli", "--count", "10", "--pump-max-seconds", "20"]
            )

        self.assertEqual(config.device_id, "node_cli")
        self.assertEqual(config.message_count, 10)
        self.assertEqual(config.pump_max_seconds, 20)

    def test_boot_id_is_generated_when_not_configured(self):
        with patch.dict("os.environ", {}, clear=True):
            first = parse_config([])
            second = parse_config([])

        self.assertTrue(first.boot_id.startswith("boot_"))
        self.assertNotEqual(first.boot_id, second.boot_id)

    def test_clock_can_be_reported_as_unsynced(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertFalse(parse_config(["--clock-unsynced"]).clock_synced)
        with patch.dict("os.environ", {"CLOCK_SYNCED": "false"}, clear=True):
            self.assertFalse(parse_config([]).clock_synced)

    def test_invalid_values_are_rejected(self):
        with patch.dict("os.environ", {}, clear=True):
            for arguments in (
                ["--port", "0"],
                ["--interval", "0"],
                ["--count", "-1"],
                ["--state-heartbeat", "0"],
                ["--pump-max-seconds", "0"],
                ["--password", "secret-only"],
                ["--device-id", "node/bad"],
                ["--boot-id", "boot bad"],
            ):
                with self.subTest(arguments=arguments):
                    with self.assertRaises(SystemExit):
                        parse_config(arguments)


class DisconnectSafetyTests(unittest.TestCase):
    def test_disconnect_stops_pump_and_reconnect_does_not_replay_on(self):
        client = FakeClient()
        simulator = Simulator(simulator_config(), client)
        simulator.on_connect(client, None, None, 0, None)
        command = pump_on_message(simulator)
        simulator.on_message(client, None, command)

        self.assertEqual(simulator.runtime.relay_state, "on")
        old_order_mark = simulator.runtime.order_mark
        old_outcomes = dict(simulator.runtime.outcomes)
        self.assertIsNotNone(simulator.runtime.pump_stop_at)

        published_before_disconnect = len(client.published)
        simulator.on_disconnect(client, None, None, 1, None)

        self.assertEqual(simulator.runtime.relay_state, "off")
        self.assertIsNone(simulator.runtime.running_command_id)
        self.assertIsNone(simulator.runtime.pump_stop_at)
        self.assertEqual(simulator.runtime.order_mark, old_order_mark)
        self.assertEqual(simulator.runtime.outcomes, old_outcomes)
        self.assertFalse(simulator.connected.is_set())
        self.assertEqual(
            len(client.published),
            published_before_disconnect,
            "disconnect callback must not publish through a dead connection",
        )

        published_before_reconnect = len(client.published)
        simulator.on_connect(client, None, None, 0, None)
        self.assertTrue(simulator.connected.is_set())
        reconnect_states = [
            payload
            for topic, payload, _qos, _retain in client.published[published_before_reconnect:]
            if topic.endswith("/state")
        ]
        self.assertEqual(reconnect_states[-1]["relay_state"], "off")

        simulator.on_message(client, None, command)
        self.assertEqual(simulator.runtime.relay_state, "off")
        self.assertIsNone(simulator.runtime.pump_stop_at)

    def test_main_registers_disconnect_callback(self):
        client = FakeClient()
        with (
            patch("simulator.parse_config", return_value=simulator_config()),
            patch("simulator.build_client", return_value=client),
            patch.object(Simulator, "run", return_value=0),
        ):
            self.assertEqual(main([]), 0)

        self.assertIsNotNone(client.on_disconnect)
        self.assertEqual(client.on_disconnect.__self__.__class__, Simulator)


if __name__ == "__main__":
    unittest.main()
