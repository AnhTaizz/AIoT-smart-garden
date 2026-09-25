-- B-W1-02: command lifecycle, device ACK/state events and last reported state.
CREATE TABLE command (
    command_id UUID PRIMARY KEY,
    device_id TEXT NOT NULL,
    action TEXT NOT NULL,
    params JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL
        CHECK (status IN ('pending', 'applied', 'rejected', 'timeout')),
    device_ack TEXT CHECK (device_ack IN ('accepted', 'rejected', 'applied')),
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    published_at TIMESTAMPTZ,
    acked_at TIMESTAMPTZ,
    finalized_at TIMESTAMPTZ,
    state_confirmed_at TIMESTAMPTZ,
    late_ack TEXT CHECK (late_ack IN ('accepted', 'rejected', 'applied')),
    late_ack_at TIMESTAMPTZ
);

CREATE INDEX command_device_created_idx ON command (device_id, created_at DESC);
CREATE INDEX command_pending_expiry_idx ON command (expires_at)
    WHERE status = 'pending';

CREATE TABLE command_event (
    id BIGSERIAL PRIMARY KEY,
    command_id UUID,
    device_id TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('ack', 'state')),
    ack_status TEXT,
    late BOOLEAN NOT NULL DEFAULT false,
    payload JSONB NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX command_event_command_idx ON command_event (command_id, id);

CREATE TABLE device_state (
    device_id TEXT PRIMARY KEY,
    mode TEXT,
    relay_state TEXT,
    last_command_id UUID,
    reported_at TIMESTAMPTZ,
    received_at TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL
);
