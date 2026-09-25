import unittest
from unittest.mock import patch

from simulator import parse_config, topic_for


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


if __name__ == "__main__":
    unittest.main()
