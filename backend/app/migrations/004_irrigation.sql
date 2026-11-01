CREATE TABLE irrigation_profile (
 device_id TEXT PRIMARY KEY,
 enabled BOOLEAN NOT NULL DEFAULT false,
 revision BIGINT NOT NULL DEFAULT 1,
 policy JSONB NOT NULL,
 next_evaluation TIMESTAMPTZ NOT NULL DEFAULT now(),
 lease_until TIMESTAMPTZ,
 lease_token UUID,
 last_attempt TIMESTAMPTZ,
 last_status TEXT NOT NULL DEFAULT 'manual'
);
CREATE TABLE irrigation_decision (
 id UUID PRIMARY KEY,
 device_id TEXT NOT NULL REFERENCES irrigation_profile(device_id),
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 observation JSONB NOT NULL,
 proposal JSONB,
 status TEXT NOT NULL,
 reason TEXT NOT NULL,
 reserved_seconds INTEGER NOT NULL DEFAULT 0,
 command_id UUID
);
CREATE INDEX irrigation_decision_recent ON irrigation_decision(device_id, created_at DESC);
