import random
import unittest
import uuid
from datetime import datetime, timedelta, timezone

from device import DeviceRuntime, new_boot_id

NOW = datetime(2026, 9, 25, 9, 11, 0, tzinfo=timezone.utc)


def command_uuid(label):
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"smart-garden-test:{label}"))


def control(
    device,
    action="pump_on",
    sequence=1,
    duration=10,
    command_id="c1",
    target_boot_id="__self__",
    expires_in=15,
):
    payload = {
        "schema": "command-v1",
        "command_id": command_uuid(command_id),
        "device_id": device.device_id,
        "command_sequence": sequence,
        "action": action,
        "params": {} if action == "pump_off" else {"duration_seconds": duration},
        "target_boot_id": device.boot_id if target_boot_id == "__self__" else target_boot_id,
        "issued_at": NOW.isoformat(),
        "expires_at": (NOW + timedelta(seconds=expires_in)).isoformat(),
    }
    if action == "pump_off":
        payload["target_boot_id"] = None
    return payload


def new_device(**kwargs):
    return DeviceRuntime(device_id="node_test", boot_id=new_boot_id(), **kwargs)


class TelemetryPayloadTests(unittest.TestCase):
    def test_payload_is_labelled_simulated_and_complete(self):
        device = new_device()
        payload = device.telemetry_payload(random.Random(7))

        self.assertEqual(payload["schema"], "telemetry-v1")
        self.assertIs(payload["simulated"], True)
        self.assertEqual(payload["sequence"], 1)
        self.assertEqual(payload["boot_id"], device.boot_id)
        self.assertTrue(payload["measured_at"].endswith("Z"))
        self.assertEqual(payload["sensor_status"], {"aht20": "ok", "soil": "ok"})
        self.assertEqual(device.telemetry_payload(random.Random(7))["sequence"], 2)

    def test_unsynced_clock_sends_no_timestamp(self):
        payload = new_device(clock_synced=False).telemetry_payload(random.Random(1))

        self.assertIs(payload["clock_synced"], False)
        self.assertIsNone(payload["measured_at"])

    def test_sensor_error_reports_null_not_zero(self):
        payload = new_device().telemetry_payload(random.Random(1), aht20_ok=False)

        self.assertIsNone(payload["temperature_c"])
        self.assertIsNone(payload["air_humidity_pct"])
        self.assertEqual(payload["sensor_status"]["aht20"], "error")
        self.assertIsNotNone(payload["soil_moisture_pct"])


class PumpOnTests(unittest.TestCase):
    def test_valid_command_starts_the_pump(self):
        device = new_device()
        decision = device.handle_command(control(device), NOW, monotonic=100.0)

        self.assertEqual(decision.status, "applied")
        self.assertEqual(device.relay_state, "on")
        self.assertEqual(device.order_mark, 1)
        self.assertEqual(device.pump_stop_at, 110.0)

    def test_expired_command_never_runs(self):
        device = new_device()
        decision = device.handle_command(
            control(device, expires_in=-1), NOW, monotonic=100.0
        )

        self.assertEqual((decision.status, decision.reason), ("rejected", "expired"))
        self.assertEqual(device.relay_state, "off")

    def test_unsynced_clock_refuses_pump_on(self):
        device = new_device(clock_synced=False)
        decision = device.handle_command(control(device), None, monotonic=100.0)

        self.assertEqual(
            (decision.status, decision.reason), ("rejected", "clock_unsynced")
        )
        self.assertEqual(device.relay_state, "off")

    def test_command_for_another_boot_is_refused(self):
        device = new_device()
        decision = device.handle_command(
            control(device, target_boot_id="boot_someoldone"), NOW, monotonic=1.0
        )

        self.assertEqual(
            (decision.status, decision.reason), ("rejected", "boot_mismatch")
        )
        self.assertEqual(device.relay_state, "off")

    def test_duration_above_the_local_limit_is_refused(self):
        device = new_device(pump_max_seconds=30)
        decision = device.handle_command(
            control(device, duration=31), NOW, monotonic=1.0
        )

        self.assertEqual(
            (decision.status, decision.reason), ("rejected", "invalid_duration")
        )

    def test_second_pump_on_while_running_is_busy(self):
        device = new_device()
        device.handle_command(control(device), NOW, monotonic=100.0)
        decision = device.handle_command(
            control(device, command_id="c2", sequence=2), NOW, monotonic=101.0
        )

        self.assertEqual((decision.status, decision.reason), ("rejected", "busy"))
        self.assertEqual(device.running_command_id, command_uuid("c1"))
        self.assertEqual(device.pump_stop_at, 110.0)

    def test_unsupported_action_and_bad_sequence(self):
        device = new_device()
        self.assertEqual(
            device.handle_command(
                control(device, action="open_valve"), NOW, monotonic=1.0
            ).reason,
            "unsupported_action",
        )
        payload = control(device, command_id="c2")
        payload["command_sequence"] = "7"
        self.assertEqual(
            device.handle_command(payload, NOW, monotonic=1.0).reason,
            "invalid_payload",
        )

    def test_invalid_command_envelope_is_rejected_before_execution(self):
        device = new_device()
        cases = []
        for key in ("schema", "issued_at", "expires_at", "params"):
            payload = control(device, command_id=f"missing-{key}")
            del payload[key]
            cases.append(payload)
        cases.append(
            {
                **control(device, command_id="wrong-schema"),
                "schema": "command-v2",
            }
        )
        cases.append(
            {
                **control(device, command_id="extra-param"),
                "params": {"duration_seconds": 10, "unexpected": True},
            }
        )

        for payload in cases:
            with self.subTest(payload=payload):
                decision = device.handle_command(payload, NOW, monotonic=1.0)
                self.assertEqual(
                    (decision.status, decision.reason),
                    ("rejected", "invalid_payload"),
                )
                self.assertEqual(device.relay_state, "off")

    def test_invalid_command_id_is_ignored_and_missing_device_is_rejected(self):
        device = new_device()
        invalid_id = control(device)
        invalid_id["command_id"] = "not-a-uuid"
        self.assertIsNone(
            device.handle_command(invalid_id, NOW, monotonic=1.0).status
        )

        missing_device = control(device, command_id="missing-device")
        del missing_device["device_id"]
        decision = device.handle_command(missing_device, NOW, monotonic=1.0)
        self.assertEqual(
            (decision.status, decision.reason), ("rejected", "invalid_payload")
        )

    def test_command_for_another_device_gets_no_ack(self):
        device = new_device()
        payload = control(device)
        payload["device_id"] = "someone_else"

        decision = device.handle_command(payload, NOW, monotonic=1.0)
        self.assertIsNone(decision.status)
        self.assertEqual(device.outcomes, {})


class DuplicateAndOrderingTests(unittest.TestCase):
    def test_duplicate_command_neither_reruns_nor_extends_the_pump(self):
        device = new_device()
        device.handle_command(control(device), NOW, monotonic=100.0)
        repeat = device.handle_command(control(device), NOW, monotonic=105.0)

        self.assertEqual(repeat.status, "applied")
        self.assertTrue(repeat.duplicate)
        self.assertEqual(device.pump_stop_at, 110.0, "timer must not be extended")

    def test_duplicate_of_a_rejected_command_returns_the_same_reason(self):
        device = new_device()
        first = device.handle_command(
            control(device, expires_in=-1), NOW, monotonic=100.0
        )
        repeat = device.handle_command(
            control(device, expires_in=-1), NOW, monotonic=101.0
        )

        self.assertEqual(repeat.reason, first.reason)
        self.assertTrue(repeat.duplicate)
        self.assertEqual(device.relay_state, "off")

    def test_stop_then_older_pump_on_does_not_start_the_pump(self):
        device = new_device()
        # STOP is issued second (sequence 2) but arrives first.
        stop = device.handle_command(
            control(device, action="pump_off", command_id="off", sequence=2),
            NOW,
            monotonic=100.0,
        )
        self.assertEqual(stop.status, "applied")

        late_on = device.handle_command(
            control(device, command_id="on-older", sequence=1), NOW, monotonic=101.0
        )
        self.assertEqual(
            (late_on.status, late_on.reason), ("rejected", "superseded")
        )
        self.assertEqual(device.relay_state, "off")

    def test_a_newer_pump_on_after_stop_still_works(self):
        device = new_device()
        device.handle_command(
            control(device, action="pump_off", command_id="off", sequence=2),
            NOW,
            monotonic=100.0,
        )
        decision = device.handle_command(
            control(device, command_id="on-newer", sequence=3), NOW, monotonic=101.0
        )

        self.assertEqual(decision.status, "applied")
        self.assertEqual(device.relay_state, "on")

    def test_old_or_repeated_stop_never_lowers_the_order_mark(self):
        device = new_device()
        device.handle_command(
            control(device, action="pump_off", command_id="off-9", sequence=9),
            NOW,
            monotonic=100.0,
        )
        device.handle_command(
            control(device, action="pump_off", command_id="off-4", sequence=4),
            NOW,
            monotonic=101.0,
        )

        self.assertEqual(device.order_mark, 9)
        blocked = device.handle_command(
            control(device, command_id="on-5", sequence=5), NOW, monotonic=102.0
        )
        self.assertEqual(blocked.reason, "superseded")


class StopAndRebootTests(unittest.TestCase):
    def test_pump_off_ignores_expiry_boot_and_busy(self):
        device = new_device()
        device.handle_command(control(device), NOW, monotonic=100.0)
        payload = control(
            device, action="pump_off", command_id="off", sequence=2, expires_in=-120
        )

        decision = device.handle_command(payload, NOW, monotonic=105.0)
        self.assertEqual(decision.status, "applied")
        self.assertEqual(device.relay_state, "off")
        self.assertIsNone(device.running_command_id)

    def test_pump_off_works_without_a_synced_clock(self):
        device = new_device(clock_synced=False)
        decision = device.handle_command(
            control(device, action="pump_off", command_id="off", sequence=1),
            None,
            monotonic=1.0,
        )

        self.assertEqual(decision.status, "applied")

    def test_pump_off_when_already_off_is_still_applied(self):
        device = new_device()
        decision = device.handle_command(
            control(device, action="pump_off", command_id="off", sequence=1),
            NOW,
            monotonic=1.0,
        )

        self.assertEqual(decision.status, "applied")
        self.assertEqual(device.relay_state, "off")

    def test_pump_stops_by_itself_after_the_duration(self):
        device = new_device()
        device.handle_command(control(device, duration=5), NOW, monotonic=100.0)

        self.assertFalse(device.pump_finished(104.0))
        self.assertEqual(device.relay_state, "on")
        self.assertTrue(device.pump_finished(105.0))
        self.assertEqual(device.relay_state, "off")
        self.assertFalse(device.pump_finished(106.0))
        # The command that started it is still the last applied one.
        self.assertEqual(device.last_command_id, command_uuid("c1"))

    def test_reboot_clears_pump_order_mark_and_command_memory(self):
        device = new_device()
        device.handle_command(control(device, sequence=5), NOW, monotonic=100.0)
        old_boot = device.boot_id

        device.reboot()

        self.assertNotEqual(device.boot_id, old_boot)
        self.assertEqual(device.relay_state, "off")
        self.assertEqual(device.order_mark, 0)
        self.assertEqual(device.outcomes, {})
        # A command aimed at the boot that died is refused.
        decision = device.handle_command(
            control(device, command_id="c9", sequence=6, target_boot_id=old_boot),
            NOW,
            monotonic=200.0,
        )
        self.assertEqual(decision.reason, "boot_mismatch")


if __name__ == "__main__":
    unittest.main()
