-- 003_add_device_code.sql — store device code flow state in database.

ALTER TABLE user_tokens ADD COLUMN IF NOT EXISTS device_code TEXT;
ALTER TABLE user_tokens ADD COLUMN IF NOT EXISTS user_code TEXT;
ALTER TABLE user_tokens ADD COLUMN IF NOT EXISTS verification_uri TEXT;
ALTER TABLE user_tokens ADD COLUMN IF NOT EXISTS device_code_expires_at DOUBLE PRECISION NOT NULL DEFAULT 0;
