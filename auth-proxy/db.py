"""
Postgres persistence for per-key OAuth tokens.

api_key is the sole identity (PRIMARY KEY of user_tokens — see migration
004_api_key_identity.sql). The value comes from the X-Api-Key header;
tokens, decoded claims, device-flow state and the per-key MCP session ids for
trino-mcp / mcp-superset all live on the same row.

Uses psycopg3 async with a connection pool and plain SQL (no ORM). The schema
lives in migrations/*.sql and is applied at startup by run_migrations().
"""

import asyncio
import glob
import logging
import os

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

    last_exc: Exception | None = None
    for attempt in range(1, 11):
        # A pool that failed to open cannot be reused — build a fresh one
        # for every attempt.
        pool = AsyncConnectionPool(DATABASE_URL, min_size=1, max_size=10, open=False)
        try:
            await pool.open(wait=True, timeout=5.0)
            _pool = pool
            log.info("[db] Pool opened (attempt %d)", attempt)
            return
        except Exception as exc:  # noqa: BLE001 — retry any connect error
            last_exc = exc
            log.warning("[db] Pool open failed (attempt %d/10): %s", attempt, exc)
            await pool.close()
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


# ── Token CRUD (keyed by api_key) ───────────────────────────────────────────

# Columns upsert_by_api_key is allowed to touch. token_claims needs a Jsonb
# wrapper; everything else passes through as-is.
_UPSERTABLE_COLUMNS = (
    "access_token",
    "refresh_token",
    "expires_at",
    "token_claims",
    "upstream_session_id",
    "superset_session_id",
)


async def get_by_api_key(api_key: str | None) -> dict | None:
    """Return the user_tokens row for an api_key as a dict, or None."""
    if not api_key:
        return None
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT api_key, access_token, refresh_token, expires_at, "
                "token_claims, upstream_session_id, superset_session_id, "
                "device_code, user_code, verification_uri, device_code_expires_at "
                "FROM user_tokens WHERE api_key = %s",
                (api_key,),
            )
            return await cur.fetchone()


async def upsert_by_api_key(api_key: str, fields: dict) -> None:
    """Insert or update the row for an api_key with the given column values.
    Only whitelisted columns are written; unknown keys raise so a typo can't
    silently drop data."""
    unknown = set(fields) - set(_UPSERTABLE_COLUMNS)
    if unknown:
        raise ValueError(f"upsert_by_api_key: unknown columns {sorted(unknown)}")
    if not fields:
        return

    columns = [c for c in _UPSERTABLE_COLUMNS if c in fields]
    values = [
        Jsonb(fields[c]) if c == "token_claims" and fields[c] is not None else fields[c]
        for c in columns
    ]
    col_list = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(columns))
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in columns)

    pool = get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            f"INSERT INTO user_tokens (api_key, {col_list}, updated_at) "
            f"VALUES (%s, {placeholders}, now()) "
            f"ON CONFLICT (api_key) DO UPDATE SET {updates}, updated_at = now()",
            (api_key, *values),
        )
        await conn.commit()


async def clear_tokens(api_key: str) -> None:
    """Null out the tokens for an api_key (e.g. when the refresh token is
    rejected). Keeps the row so session ids and claims history remain."""
    pool = get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            "UPDATE user_tokens SET access_token = NULL, refresh_token = NULL, "
            "expires_at = 0, updated_at = now() WHERE api_key = %s",
            (api_key,),
        )
        await conn.commit()


# ── Device code flow state ──────────────────────────────────────────────────

async def save_device_flow_state(
    api_key: str,
    device_code: str | None,
    user_code: str | None,
    verification_uri: str | None,
    device_code_expires_at: float,
) -> None:
    """Persist the pending device-code flow so login instructions survive a
    proxy restart (the in-memory poll task does not — see azure/oauth.py)."""
    pool = get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            "INSERT INTO user_tokens (api_key, device_code, user_code, "
            "verification_uri, device_code_expires_at, updated_at) "
            "VALUES (%s, %s, %s, %s, %s, now()) "
            "ON CONFLICT (api_key) DO UPDATE SET "
            "device_code = EXCLUDED.device_code, "
            "user_code = EXCLUDED.user_code, "
            "verification_uri = EXCLUDED.verification_uri, "
            "device_code_expires_at = EXCLUDED.device_code_expires_at, "
            "updated_at = now()",
            (api_key, device_code, user_code, verification_uri, device_code_expires_at),
        )
        await conn.commit()


# ── Per-key upstream session ids ────────────────────────────────────────────

async def _get_session_col(api_key: str, column: str) -> str | None:
    pool = get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                f"SELECT {column} FROM user_tokens WHERE api_key = %s", (api_key,)
            )
            row = await cur.fetchone()
            return row[0] if row else None


async def _set_session_col(api_key: str, column: str, session_id: str | None) -> None:
    """Set a session-id column, creating the row if the api_key has none yet."""
    pool = get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            f"INSERT INTO user_tokens (api_key, {column}, updated_at) "
            f"VALUES (%s, %s, now()) "
            f"ON CONFLICT (api_key) DO UPDATE SET {column} = EXCLUDED.{column}, "
            f"updated_at = now()",
            (api_key, session_id),
        )
        await conn.commit()


async def get_upstream_session(api_key: str) -> str | None:
    return await _get_session_col(api_key, "upstream_session_id")


async def set_upstream_session(api_key: str, session_id: str | None) -> None:
    await _set_session_col(api_key, "upstream_session_id", session_id)


async def get_superset_session(api_key: str) -> str | None:
    return await _get_session_col(api_key, "superset_session_id")


async def set_superset_session(api_key: str, session_id: str | None) -> None:
    await _set_session_col(api_key, "superset_session_id", session_id)
