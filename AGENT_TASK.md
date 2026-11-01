# Task for local AI coding agent — Smart Garden

Read `AGENTS.md` first. Then inspect **the whole current repository**, not merely the attached firmware snapshot. In particular, locate and read:
- firmware source, configuration examples, PlatformIO/Arduino build settings, Wokwi diagram;
- `docs/INTERFACES.md`, contract G02 and any additional schema/decision documents;
- existing MQTT broker settings, backend/API, AI decision integration, database, dashboard and tests.

**Goal:** Implement or complete the real ESP32 firmware so that it integrates safely with the project's existing server-driven AI irrigation architecture. ESP32 reads AHT20 + capacitive soil probe, publishes telemetry and device status, receives server-issued MQTT pump commands, validates them, activates the existing CW-020 relay via GPIO26, and enforces local OFF/timeout/disconnect safety. Keep all existing protocol compatibility. The physical relay IN uses an **experimental pair of series diodes** between GPIO26 and IN, and direct 3.3V HIGH did not turn it off; do not assume the hardware input is a safe standard GPIO interface.

**Do this in stages:**
1. Map project architecture and list current files plus missing/uncertain requirements, explicitly flagging things absent from repo.
2. Show a short implementation plan and prioritize safety. Reuse code and schemas rather than rewriting entire project.
3. Make code changes with testable separation between actual relay output and mock/dry-run modes. Keep pump disabled in test mode.
4. Build, run available automated tests and add regression tests for 60-second bound, millis overflow, Wi-Fi/MQTT loss, command expiry, duplicates, wrong device/boot ID, malformed JSON, disconnected sensors, restart state.
5. Report changed files, how to configure private MQTT broker safely, precise upload steps for ESP32 Dev Module, and a **manual test sequence that begins with the pump's 5V adapter unplugged**.

**Hard restrictions:**
- Do NOT control, power, or flash physical hardware without my explicit permission.
- Do NOT send real pump-ON commands as a test.
- Do NOT assume the simulation's ESP32 5V load circuit applies to the physical pump; its power is separate (5V adapter through relay COM/NO).
- Do NOT discard/rename existing MQTT fields or change backend protocol without clearly identifying the compatibility impact.
- Do NOT silently assume soil calibration values, electrical safety of the two diodes, secure MQTT credentials, or a proven independent hard 60-second timer.

**First response I expect:** state the architecture you found, the repository paths you inspected, the major gaps/risks and a concrete implementation plan. Then proceed to implement and test software changes within the authorized local repo.
