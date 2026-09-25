-- G02 v1 contract: telemetry boot/clock/sensor fields, per-command state
-- evidence, boot tracking and an atomic per-device command sequence.

-- Telemetry: measured_at is null when the device has no trustworthy clock.
ALTER TABLE telemetry
    ADD COLUMN boot_id TEXT,
    ADD COLUMN clock_synced BOOLEAN,
    ADD COLUMN uptime_ms BIGINT,
    ADD COLUMN sensor_status JSONB,
    ALTER COLUMN measured_at DROP NOT NULL;

-- Rows stored before this migration have no boot_id. Give each one its own
-- synthetic boot so the deduplication index below cannot fail on pre-v1 data,
-- and so no legacy row pretends to share a boot with another.
UPDATE telemetry
   SET boot_id = 'legacy_' || id::text,
       clock_synced = true,
       uptime_ms = 0,
       sensor_status = '{"aht20": "ok", "soil": "ok"}'::jsonb
 WHERE boot_id IS NULL;

ALTER TABLE telemetry
    ALTER COLUMN boot_id SET NOT NULL,
    ALTER COLUMN clock_synced SET NOT NULL,
    ALTER COLUMN uptime_ms SET NOT NULL,
    ALTER COLUMN sensor_status SET NOT NULL;

-- Deduplication: the same reading resent by a device is ignored, not rejected.
CREATE UNIQUE INDEX telemetry_device_boot_sequence_key
    ON telemetry (device_id, boot_id, sequence);

-- Commands carry their ordering position and the boot they were aimed at.
ALTER TABLE command
    ADD COLUMN command_sequence BIGINT,
    ADD COLUMN target_boot_id TEXT,
    ADD COLUMN ack_boot_id TEXT,
    ADD COLUMN confirmed_relay_state TEXT
        CHECK (confirmed_relay_state IN ('on', 'off')),
    ADD COLUMN confirmed_state_sequence BIGINT,
    ADD COLUMN confirmed_boot_id TEXT;

UPDATE command SET command_sequence = 0 WHERE command_sequence IS NULL;
ALTER TABLE command ALTER COLUMN command_sequence SET NOT NULL;

CREATE INDEX command_device_sequence_idx
    ON command (device_id, command_sequence DESC);

-- The sequence counter lives in PostgreSQL so it survives backend restarts.
CREATE TABLE device_command_counter (
    device_id TEXT PRIMARY KEY,
    last_sequence BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Every boot the backend has ever seen, so a late message from a dead boot is
-- recognisable and cannot make the backend fall back to it.
CREATE TABLE device_boot (
    device_id TEXT NOT NULL,
    boot_id TEXT NOT NULL,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (device_id, boot_id)
);

ALTER TABLE device_state
    ADD COLUMN boot_id TEXT,
    ADD COLUMN state_sequence BIGINT,
    ADD COLUMN last_command_sequence BIGINT,
    ADD COLUMN clock_synced BOOLEAN;

-- device_state rows from the pre-v1 schema cannot be mapped to a boot; drop
-- them so the new NOT NULL columns describe real reported state only.
DELETE FROM device_state WHERE boot_id IS NULL;

ALTER TABLE device_state
    ALTER COLUMN boot_id SET NOT NULL,
    ALTER COLUMN state_sequence SET NOT NULL,
    ALTER COLUMN clock_synced SET NOT NULL,
    ALTER COLUMN mode SET NOT NULL,
    ALTER COLUMN relay_state SET NOT NULL;

ALTER TABLE command_event
    ADD COLUMN boot_id TEXT,
    ADD COLUMN outcome TEXT;
