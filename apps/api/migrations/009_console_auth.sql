-- Local console administrator identity and opaque session state.
-- Passwords and session tokens are created by the API, never by SQL.
CREATE TABLE IF NOT EXISTS console_admins (
    username TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    must_change_password BOOLEAN NOT NULL DEFAULT TRUE,
    password_version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    password_changed_at TIMESTAMPTZ,
    initial_password_issued_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS console_sessions (
    session_hash TEXT PRIMARY KEY,
    username TEXT NOT NULL REFERENCES console_admins(username),
    kind TEXT NOT NULL CHECK (kind IN ('password_change', 'authenticated')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS console_sessions_user_idx
    ON console_sessions (username, expires_at);

CREATE TABLE IF NOT EXISTS console_login_attempts (
    bucket_key TEXT PRIMARY KEY,
    failures INTEGER NOT NULL DEFAULT 0,
    first_failure_at TIMESTAMPTZ,
    last_failure_at TIMESTAMPTZ
);
