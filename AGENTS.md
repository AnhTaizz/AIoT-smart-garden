# Smart Garden — Context and guardrails for coding agents

> **Integration note (2026-11-01):** the statement below that "the server runs the AI model and makes irrigation decisions" is **not a team decision yet**. `main` now follows it: PR #9 added the backend supervisor and PR #10 lets it drive a real ESP32 only when the device ID is listed in `IRRIGATION_REAL_DEVICE_IDS` and the broker uses credentials. It still conflicts with `CLAUDE.md` §3 (ESP32 owns Manual/Auto; no second backend auto-watering logic) and with the W3 plan. See `docs/INTERFACES.md` (Ranh giới xử lý). Until Thành, Tài and Toản record the decision, keep `IRRIGATION_REAL_DEVICE_IDS` empty outside supervised sessions and do not add Auto to the firmware.

> Read this file before changing code. This document describes the **real hardware reported and tested by the user**, plus the original firmware files shared in the conversation. **Do not assume that a Wokwi diagram describes physical power wiring.**

## 1. Goal and architecture

Build a complete, maintainable ESP32 firmware integrated with the **existing** Smart Garden server/backend, MQTT contract, and an AI-based irrigation decision system.

- There is currently **one physical ESP32 node** (`node_01` by default).
- The **server runs the AI model and makes irrigation decisions**. The ESP32 samples and reports sensor measurements, receives validated commands, executes them, reports acknowledgements and device state, and enforces local safety protections.
- This corresponds to an intended *centralized AI decision* architecture, discussed as IoT Level 3. A future Level 6 (multiple independent nodes, centrally coordinated) is a possible roadmap, **not a license to rewrite or expand the current scope without request**.
- **Never invent API fields, MQTT payload schemas, topics, database tables, or backend behavior.** Read the actual repository, especially any `docs/INTERFACES.md` and protocol/decision documents, and preserve the established contract.

## 2. Hardware (real rig, not Wokwi)

| Part | Confirmed physical wiring / specification |
| --- | --- |
| Board | ESP32 DevKit V1 / ESP-32D, Arduino IDE board selection `ESP32 Dev Module` |
| AHT20 | VIN -> ESP32 3V3; GND -> ESP32 GND; SDA -> GPIO21; SCL -> GPIO22 |
| Capacitive soil sensor v1.2 | VCC -> ESP32 3V3; GND -> ESP32 GND; AOUT -> GPIO34 (ADC1) |
| Relay module | CW-020, marked `Low level trigger`, SONGLE SRD-05VDC-SL-C 5V coil; VCC -> ESP32 5V USB rail; GND -> ESP32 GND |
| Relay input | ESP32 GPIO26 -> **two series axial diodes** -> relay IN; the **banded/cathode ends point towards GPIO26**. The user tested this experimentally to enable ON/OFF switching. |
| Pump | Small DC pump advertised as **3–5V, 100–200mA**. Red lead nominal +, black nominal −. Seller advises avoiding long continuous 5V operation. Actual motor start/stall current not measured. |
| Pump supply | Separate 5V/5A DC adapter via marked (+)/(−) screw terminal breakout. + -> relay COM, relay NO -> red pump wire, black pump wire -> adapter −. NC unused. Pump does not draw supply through ESP32. |

**Known experimental results:**
- AHT20 and soil sensor were reported working on the physical board with Arduino test firmware.
- Relay with input left open: power LED lit; relay input shorted to GND: additional LED lit and relay clicks.
- GPIO26 directly connected to relay IN: relay remained energized even when firmware commanded GPIO HIGH (3.3V), so **direct connection is NOT an accepted working configuration**.
- With the two series diodes on IN, user reported successful relay OFF at startup, OFF command, timed ON (2 s), automatic OFF, and reset/restart tests.
- **Pump was subsequently connected and user reported it successfully ran.** This does NOT prove safe long-term electrical operation.

**Important engineering caveat:** The two-diode workaround is experimentally functional, but the module input schematic, exact diode part numbers, GPIO injection current, and startup/shutdown transients were **not measured or formally validated**. Do not describe it as a proven safe level shifter. Do not casually rewire it, tie 5V directly to a GPIO, or enable unattended pumping. Recommend electrical verification and a proper interface for sustained deployment. Do not assume hardware changes are available unless user authorizes them.

### Physical safety invariants

1. Pump **OFF by default** during normal startup and on communication loss; note that software cannot guarantee OFF in all boot/reset/brownout states or with welded relay contacts.
2. `pump_on` runtime must be bounded to **1..60 seconds** (or stricter user-approved policy); locally turn OFF on timeout, independent of AI/server messages.
3. A firmware watchdog and `millis()` timeout are software mechanisms; they do **not** provide a guaranteed independent hardware power cut-off.
4. No motor power from ESP32 `3V3`, `5V`, or GPIO. Pump uses the separate adapter via COM/NO dry contacts.
5. On real hardware, never automatically run a pump just because firmware was flashed, MQTT connected, or telemetry started. Test OFF states first with pump supply disconnected.
6. Relay + water: low-voltage DC only. Keep motor/adapter connections dry and properly insulated.
7. Sensor failures must be encoded as errors/null, never silently as real 0% humidity.

## 3. Original supplied firmware/project material

The conversation supplied files named `README.md`, `diagram.json`, `config(1).h`, `main.cpp`. These are **a snapshot**, not necessarily identical to the latest code in the user's local repo. The coding agent must inspect the actual files and Git diff rather than assume they match this snapshot.

The snapshot's README points to repo paths resembling `firmware/src/main.cpp`, `firmware/include/config.h`, `firmware/diagram.json`, `docs/INTERFACES.md`. Verify actual locations first.

Observed configuration and library use in the snapshot:
- Arduino/ESP32; `Wire`, `Adafruit_AHTX0`, `WiFi`, `PubSubClient`, `ArduinoJson` (v7-style `JsonDocument`), `time.h`.
- `PIN_I2C_SDA=21`, `PIN_I2C_SCL=22`, `PIN_SOIL_ADC=34`, `PIN_RELAY=26`, `RELAY_ACTIVE_LEVEL=LOW`.
- `SOIL_ADC_DRY=3200`, `SOIL_ADC_WET=1400` are **placeholder calibration values**, not verified wet/dry measurements from the actual probe.
- `PUMP_MAX_SECONDS=60`; telemetry interval 10s; state heartbeat interval 15s.
- Default `DEVICE_ID=node_01`, `IS_SIMULATED=false`.
- Default Wi-Fi `Wokwi-GUEST` and public broker `broker.emqx.io:1883` are demo defaults **not suitable as trusted production control endpoints**. Use a private/authenticated broker and safe credential handling; do not commit real credentials.
- MQTT topics are derived as `garden/<device_id>/telemetry`, `/control`, `/ack`, `/state`.
- Data schemas are tagged `telemetry-v1`, `command-v1`, `ack-v1`, and `state-v1` in original source.
- `pump_on` uses `params.duration_seconds` and checks `target_boot_id`, `expires_at`, `command_sequence` / order, duplicate `command_id`, clock sync, busy status. `pump_off` is prioritized. Preserve the validated contract, even if implementation changes.
- Runtime errors are represented using `sensor_status.aht20` / `.soil` and null numeric measurements.
- Wokwi uses a potentiometer as a **simulation** of soil ADC and a relay-driven LED as a **simulation** of the load; its relay COM connects to simulated ESP32 5V. **Never copy that simulated pump-power arrangement to real hardware.**

## 4. Items in original code that REQUIRE REVIEW, not silent assumptions

1. **Relay boot sequencing:** original snapshot calls `pinMode(PIN_RELAY, OUTPUT)` before `setRelay(OFF)`; prepare inactive output latch first and verify actual IN logic/hardware fail-safe, but no software-only guarantee during reset.
2. **Timer wraparound:** original stores `pumpStopMillis = millis() + duration_ms` then compares `currentMillis >= pumpStopMillis`. Prefer unsigned elapsed-time subtraction; test the wraparound behavior.
3. **Blocking operations:** MQTT/Wi-Fi reconnection and callback work may delay timeout processing; assess watchdog/liveness and ensure a rapid OFF path.
4. **JSON validation:** original code obtains `action` and later calls `strcmp(action, ...)` without an explicit null check. Validate all expected fields and types before dereferencing; enforce lengths and format.
5. **Expiry validation:** original `parseIsoUtc` uses `sscanf` + `mktime`, with weak input/UTC validation; invalid/missing `expires_at` may not be rejected. Fix according to repo protocol rules, not guessed rules.
6. **String bounds:** audit `strncpy` and null termination of IDs/status/reasons; audit command cache initialization and malformed inputs.
7. **Fail-safe telemetry/status:** lost Wi-Fi/MQTT and sensor errors must not incorrectly report a healthy/active pump; ensure state transitions are internally consistent.
8. **Real probe calibration:** distinguish raw ADC from estimated percentage; permit calibration without rewriting protocol; detect disconnected/saturated ADC conservatively.
9. **MQTT security:** do not issue physically actionable pump commands based on unauthenticated public broker traffic.
10. **Validation gap:** no evidence was provided of successful end-to-end AI-server + ESP32 MQTT irrigation; the physical test used separate Arduino sketches. Do not claim integrated system already works.

## 5. Workflow required of the coding agent

1. Inspect repository layout, Git status, main firmware, config, protocol docs, server AI/backend, MQTT schemas, testing tools. Identify actual entrypoints before edits.
2. Produce a concise architecture map and a **gap analysis**: working code vs intended behavior vs missing/uncertain requirements. Clearly distinguish code evidence from user-reported hardware observations.
3. Propose a small implementation plan and file list; prefer minimal changes preserving established interfaces. Do not unilaterally create a new backend or replace schemas.
4. Implement integration end to end: sensor acquisition + calibration/error handling; MQTT connection/reconnect; server command validation; relay state; pump stop on timeout/disconnect; telemetry, ACK, state.
5. Add testability without turning on the physical pump: injectable/mock relay driver or compile-time `DRY_RUN`/simulation mode with a safe default; never silently substitute simulation in actual device reporting.
6. Build and run software tests. Test malformed MQTT payloads, duplicates, expired commands, wrong target boot/device, over-60s duration, lost connection, timer overflow, invalid sensor data, startup/reset, and ON/OFF sequences. Where physical access is impossible, report tests as unverified.
7. Summarize changed files, commands used, build/test results, unresolved hardware risks, and step-by-step manual validation **starting with pump adapter disconnected**.
8. No changes to real hardware, no uploading/flashing to connected hardware, no power-cycling or sending pump ON commands without explicit user authorization.

## 6. Acceptance criteria (for implementation)

- Correctly compiles for user's board/configuration (PlatformIO and/or Arduino IDE as actually supported by repo).
- The same physical pins remain used; real-vs-Wokwi differences are explicit.
- Reads AHT20 + soil ADC with reasonable validation and reports errors transparently.
- Honors the **existing** command protocol, including device targeting, deduplication, freshness, and ACK/state correlation.
- Server AI makes irrigation decisions; ESP32 does **not** invent autonomous watering rules unless formally required elsewhere in repo.
- Relay remains OFF by default when control is not authorized; validated ON duration does not exceed 60 seconds; loss of broker prevents/ends pumping.
- There is a test mode that cannot energize the relay/pump.
- No hardcoded secrets; document network provisioning and safe use of private broker.
- Reports limitations honestly, especially the experimental two-diode 5V relay interface and lack of an independent physical shutoff.
