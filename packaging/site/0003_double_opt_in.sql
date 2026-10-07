-- Spec 05 §3.1.10: preserve previous records without treating them as confirmed.
ALTER TABLE waitlist ADD COLUMN status TEXT NOT NULL DEFAULT 'legacy_unconfirmed'
  CHECK (status IN ('legacy_unconfirmed', 'pending', 'confirmed'));
ALTER TABLE waitlist ADD COLUMN token_hash TEXT;
ALTER TABLE waitlist ADD COLUMN token_expires INTEGER;
ALTER TABLE waitlist ADD COLUMN confirmed_at TEXT;
CREATE UNIQUE INDEX waitlist_token_hash ON waitlist(token_hash) WHERE token_hash IS NOT NULL;
CREATE TABLE waitlist_daily_quota (
  day TEXT PRIMARY KEY,
  count INTEGER NOT NULL CHECK (count >= 0)
);
