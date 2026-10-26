-- ============================================================
-- VAULT BOT — Supabase Schema
-- Paste this entire file into Supabase → SQL Editor → Run
-- ============================================================

-- ── Users ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    user_id         BIGINT PRIMARY KEY,
    username        TEXT DEFAULT '',
    full_name       TEXT DEFAULT '',
    credits         INTEGER DEFAULT 10,
    total_earned    INTEGER DEFAULT 10,
    total_spent     INTEGER DEFAULT 0,
    lookups_done    INTEGER DEFAULT 0,
    referral_code   TEXT UNIQUE,
    referred_by     BIGINT REFERENCES users(user_id) ON DELETE SET NULL,
    referral_count  INTEGER DEFAULT 0,
    is_banned       BOOLEAN DEFAULT FALSE,
    joined_at       TIMESTAMPTZ DEFAULT NOW(),
    last_seen       TIMESTAMPTZ DEFAULT NOW()
);

-- ── History (lookups + credit transactions) ────────────────
CREATE TABLE IF NOT EXISTS history (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
    type        TEXT NOT NULL,      -- 'credit' | 'debit' | 'phone' | 'ip' etc
    amount      INTEGER DEFAULT 0,
    reason      TEXT DEFAULT '',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_history_user ON history(user_id, created_at DESC);

-- ── Admin Settings (key-value store) ───────────────────────
CREATE TABLE IF NOT EXISTS admin_settings (
    key     TEXT PRIMARY KEY,
    value   JSONB
);

-- ── Redeem Codes ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS redeem_codes (
    code        TEXT PRIMARY KEY,
    credits     INTEGER NOT NULL,
    uses        INTEGER DEFAULT 0,
    max_uses    INTEGER DEFAULT 1,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── Payments ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS payments (
    pay_id      TEXT PRIMARY KEY,
    user_id     BIGINT REFERENCES users(user_id) ON DELETE SET NULL,
    pkg_id      TEXT,
    pkg_label   TEXT,
    credits     INTEGER,
    price       INTEGER,
    utr         TEXT,
    screenshot  TEXT,               -- Telegram file_id
    status      TEXT DEFAULT 'pending',  -- pending | approved | rejected | cancelled
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);
CREATE INDEX IF NOT EXISTS idx_payments_user   ON payments(user_id);

-- ── Row Level Security (disable for service_role key) ──────
-- Service role key bypasses RLS, so you don't need to set policies.
-- If you use the anon key instead, enable RLS and add policies.
ALTER TABLE users          DISABLE ROW LEVEL SECURITY;
ALTER TABLE history        DISABLE ROW LEVEL SECURITY;
ALTER TABLE admin_settings DISABLE ROW LEVEL SECURITY;
ALTER TABLE redeem_codes   DISABLE ROW LEVEL SECURITY;
ALTER TABLE payments       DISABLE ROW LEVEL SECURITY;
