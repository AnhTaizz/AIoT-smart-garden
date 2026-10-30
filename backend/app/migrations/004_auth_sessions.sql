-- BC-02: opaque bearer sessions for the operator account.
-- Only a SHA-256 of the random token is stored, never the token itself.
CREATE TABLE IF NOT EXISTS auth_session (
    token_hash BYTEA PRIMARY KEY,
    username TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('operator', 'viewer')),
    -- Fingerprint of the configured username/password hash/role: changing any
    -- of them invalidates every existing session.
    credential_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS auth_session_expires_at_idx ON auth_session (expires_at);
