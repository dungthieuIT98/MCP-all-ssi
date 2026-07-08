"""
Postgres persistence for per-user OAuth tokens.

Replaces the old single-file JSON cache + global token_state dict. Tokens are
keyed by username (the X-Consumer-Username header Kong injects), so multiple
users hitting the shared proxy no longer overwrite each other.

Uses psycopg3 async with a connection pool and plain SQL (no ORM). The schema
lives in migrations/*.sql and is applied at startup by run_migrations().
"""

import asyncio
import glob
import logging
import os
import secrets

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

log = logging.getLogger("auth-proxy")

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://authproxy:authproxy_pw@postgres:5432/authproxy"
)
MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "migrations")

_pool: AsyncConnectionPool | None = None


async def init_pool() -> None:
    """Create the connection pool. Retries the first connection because a
    passing healthcheck does not guarantee Postgres is accepting connections yet."""
    global _pool
    if _pool is not None:
        return

    pool = AsyncConnectionPool(DATABASE_URL, min_size=1, max_size=10, open=False)

    last_exc: Exception | None = None
    for attempt in range(1, 11):
        try:
            await pool.open(wait=True, timeout=5.0)
            _pool = pool
            log.info("[db] Pool opened (attempt %d)", attempt)
            return
        except Exception as exc:  # noqa: BLE001 — retry any connect error
            last_exc = exc
            log.warning("[db] Pool open failed (attempt %d/10): %s", attempt, exc)
            await asyncio.sleep(2.0)

    raise RuntimeError(f"Could not connect to Postgres after 10 attempts: {last_exc}")


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        log.info("[db] Pool closed")


def get_pool() -> AsyncConnectionPool:
    if _pool is None:
        raise RuntimeError("DB pool not initialized — call init_pool() first")
    return _pool


async def run_migrations() -> None:
    """Apply any migrations/*.sql not yet recorded in schema_migrations, in
    filename order, each inside its own transaction."""
    pool = get_pool()

    async with pool.connection() as conn:
        # Bootstrap the ledger table so we can query applied versions.
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        await conn.commit()

        async with conn.cursor() as cur:
            await cur.execute("SELECT version FROM schema_migrations")
            applied = {row[0] for row in await cur.fetchall()}

    files = sorted(glob.glob(os.path.join(MIGRATIONS_DIR, "*.sql")))
    if not files:
        log.warning("[db] No migration files found in %s", MIGRATIONS_DIR)

    for path in files:
        version = os.path.basename(path)
        if version in applied:
            log.info("[db] Migration %s already applied, skipping", version)
            continue

        with open(path, encoding="utf-8") as f:
            sql = f.read()

        async with pool.connection() as conn:
            # psycopg runs multi-statement SQL in one implicit transaction; an
            # error rolls the whole file back so a migration is all-or-nothing.
            await conn.execute(sql)
            await conn.execute(
                "INSERT INTO schema_migrations (version) VALUES (%s)", (version,)
            )
            await conn.commit()
        log.info("[db] Applied migration %s", version)


# ── Token CRUD ────────────────────────────────────────────────────────────

async def get_tokens(username: str) -> dict | None:
    """Return the user_tokens row as a dict, or None if the user has no row."""
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT username, access_token, refresh_token, expires_at, "
                "token_claims, upstream_session_id, superset_session_id "
                "FROM user_tokens WHERE username = %s",
                (username,),
            )
            return await cur.fetchone()


async def upsert_tokens(
    username: str,
    *,
    access_token: str | None,
    refresh_token: str | None,
    expires_at: float,
    token_claims: dict | None,
) -> None:
    """Insert or update the durable tokens for a user. Does not touch the
    per-user session-id columns (those have their own setters)."""
    pool = get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            "INSERT INTO user_tokens "
            "(username, access_token, refresh_token, expires_at, token_claims, updated_at) "
            "VALUES (%s, %s, %s, %s, %s, now()) "
            "ON CONFLICT (username) DO UPDATE SET "
            "access_token = EXCLUDED.access_token, "
            "refresh_token = EXCLUDED.refresh_token, "
            "expires_at = EXCLUDED.expires_at, "
            "token_claims = EXCLUDED.token_claims, "
            "updated_at = now()",
            (username, access_token, refresh_token, expires_at,
             Jsonb(token_claims) if token_claims is not None else None),
        )
        await conn.commit()


async def get_username_by_api_key(api_key: str) -> str | None:
    """Resolve the username owning an api_key (X-Profile-Key header). None if unknown."""
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT username FROM user_tokens WHERE api_key = %s", (api_key,)
            )
            row = await cur.fetchone()
            return row[0] if row else None


async def ensure_api_key(username: str) -> str:
    """Return the user's API key, generating one on first successful login.
    Atomic via INSERT ... ON CONFLICT so concurrent calls can't produce two
    keys for the same user; retries only on the astronomically rare case of
    a token_urlsafe(32) collision across different users."""
    pool = get_pool()
    for _ in range(5):
        new_key = secrets.token_urlsafe(32)
        try:
            async with pool.connection() as conn:
                async with conn.cursor(row_factory=dict_row) as cur:
                    await cur.execute(
                        "INSERT INTO user_tokens (username, api_key, updated_at) "
                        "VALUES (%s, %s, now()) "
                        "ON CONFLICT (username) DO UPDATE SET "
                        "api_key = COALESCE(user_tokens.api_key, EXCLUDED.api_key), "
                        "updated_at = now() "
                        "RETURNING api_key",
                        (username, new_key),
                    )
                    row = await cur.fetchone()
                await conn.commit()
            return row["api_key"]
        except psycopg.errors.UniqueViolation:
            log.warning("[db] api_key collision generating for user=%s, retrying", username)
            continue
    raise RuntimeError(f"Could not generate a unique api_key for user={username} after 5 attempts")


async def clear_tokens(username: str) -> None:
    """Null out the tokens for a user (e.g. when the refresh token is rejected).
    Keeps the row so session ids and claims history remain."""
    pool = get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            "UPDATE user_tokens SET access_token = NULL, refresh_token = NULL, "
            "expires_at = 0, updated_at = now() WHERE username = %s",
            (username,),
        )
        await conn.commit()


# ── Per-user upstream session ids ───────────────────────────────────────────

async def _get_session_col(username: str, column: str) -> str | None:
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                f"SELECT {column} FROM user_tokens WHERE username = %s", (username,)
            )
            row = await cur.fetchone()
            return row[0] if row else None


async def _set_session_col(username: str, column: str, session_id: str | None) -> None:
    """Set a session-id column, creating the row if the user has none yet."""
    pool = get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            f"INSERT INTO user_tokens (username, {column}, updated_at) "
            f"VALUES (%s, %s, now()) "
            f"ON CONFLICT (username) DO UPDATE SET {column} = EXCLUDED.{column}, "
            f"updated_at = now()",
            (username, session_id),
        )
        await conn.commit()


async def get_upstream_session(username: str) -> str | None:
    return await _get_session_col(username, "upstream_session_id")


async def set_upstream_session(username: str, session_id: str | None) -> None:
    await _set_session_col(username, "upstream_session_id", session_id)


async def get_superset_session(username: str) -> str | None:
    return await _get_session_col(username, "superset_session_id")


async def set_superset_session(username: str, session_id: str | None) -> None:
    await _set_session_col(username, "superset_session_id", session_id)
