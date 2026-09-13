import json
import random
import unittest
from unittest.mock import patch

from simulator import SCHEMA_NAME, build_payload, parse_config


class PayloadTests(unittest.TestCase):
    def test_payload_is_clearly_simulated_and_json_serializable(self) -> None:
        payload = build_payload("node_test", 7, random.Random(1234))

        self.assertEqual(payload["schema"], SCHEMA_NAME)
        self.assertIs(payload["simulated"], True)
        self.assertEqual(payload["device_id"], "node_test")
        self.assertEqual(payload["sequence"], 7)
        self.assertTrue(str(payload["measured_at"]).endswith("Z"))
        self.assertIn("temperature_c", payload)
        self.assertIn("air_humidity_pct", payload)
        self.assertIn("soil_moisture_pct", payload)
        json.dumps(payload)

    @patch.dict(
        "os.environ",
        {
            "MQTT_BROKER_HOST": "broker.example",
            "MQTT_BROKER_PORT": "2883",
            "DEVICE_ID": "node_env",
            "TELEMETRY_INTERVAL_SECONDS": "3.5",
            "TELEMETRY_MESSAGE_COUNT": "4",
        },
        clear=True,
    )
    def test_environment_configuration_and_default_topic(self) -> None:
        config = parse_config([])

        self.assertEqual(config.broker, "broker.example")
        self.assertEqual(config.port, 2883)
        self.assertEqual(config.topic, "garden/node_env/telemetry")
        self.assertEqual(config.interval_seconds, 3.5)
        self.assertEqual(config.message_count, 4)

    def test_cli_takes_priority_over_environment(self) -> None:
        with patch.dict("os.environ", {"DEVICE_ID": "node_env"}, clear=True):
            config = parse_config(
                [
                    "--device-id",
                    "node_cli",
                    "--topic",
                    "custom/telemetry",
                    "--count",
                    "10",
                ]
            )

        self.assertEqual(config.device_id, "node_cli")
        self.assertEqual(config.topic, "custom/telemetry")
        self.assertEqual(config.message_count, 10)


if __name__ == "__main__":
    unittest.main()

