-- 001_init.sql — per-user OAuth token storage.
-- Applied automatically at auth-proxy startup by db.run_migrations().

CREATE TABLE IF NOT EXISTS schema_migrations (
    version     TEXT PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_tokens (
    username             TEXT PRIMARY KEY,                    -- X-Consumer-Username injected by Kong
    access_token         TEXT,
    refresh_token        TEXT,
    expires_at           DOUBLE PRECISION NOT NULL DEFAULT 0, -- epoch seconds; compared to time.time()
    token_claims         JSONB,
    upstream_session_id  TEXT,                                -- per-user MCP session with trino-mcp
    superset_session_id  TEXT,                                -- per-user MCP session with mcp-superset
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
