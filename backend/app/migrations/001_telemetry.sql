-- B-W1-01: telemetry accepted from MQTT and messages rejected by validation.
CREATE TABLE telemetry (
    id BIGSERIAL PRIMARY KEY,
    device_id TEXT NOT NULL,
    sequence BIGINT NOT NULL,
    measured_at TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    temperature_c DOUBLE PRECISION,
    air_humidity_pct DOUBLE PRECISION,
    soil_moisture_pct DOUBLE PRECISION,
    simulated BOOLEAN NOT NULL,
    payload_schema TEXT NOT NULL,
    topic TEXT NOT NULL,
    raw_payload JSONB NOT NULL
);

CREATE INDEX telemetry_device_measured_idx
    ON telemetry (device_id, measured_at DESC, id DESC);
CREATE INDEX telemetry_device_received_idx
    ON telemetry (device_id, received_at DESC, id DESC);

-- Invalid payloads are kept apart so they never look like valid telemetry.
CREATE TABLE rejected_message (
    id BIGSERIAL PRIMARY KEY,
    topic TEXT NOT NULL,
    reason TEXT NOT NULL,
    raw_payload TEXT NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
