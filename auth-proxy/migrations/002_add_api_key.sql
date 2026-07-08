-- 002_add_api_key.sql — per-user API key, generated on first successful login.

ALTER TABLE user_tokens ADD COLUMN IF NOT EXISTS api_key TEXT UNIQUE;
