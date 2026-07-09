-- 004_api_key_identity.sql — api_key becomes the sole identity; username removed.

DELETE FROM user_tokens WHERE api_key IS NULL;
ALTER TABLE user_tokens DROP CONSTRAINT IF EXISTS user_tokens_pkey;
ALTER TABLE user_tokens ALTER COLUMN api_key SET NOT NULL;
ALTER TABLE user_tokens ADD PRIMARY KEY (api_key);
ALTER TABLE user_tokens DROP COLUMN IF EXISTS username;
