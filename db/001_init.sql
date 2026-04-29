CREATE SCHEMA IF NOT EXISTS personal_xp;
SET search_path TO personal_xp, public;

CREATE TABLE IF NOT EXISTS users (
  id         SERIAL PRIMARY KEY,
  name       TEXT NOT NULL,
  email      TEXT UNIQUE NOT NULL,
  pin_hash   TEXT NOT NULL,
  role       TEXT NOT NULL DEFAULT 'owner',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS categories (
  id         SERIAL PRIMARY KEY,
  name       TEXT NOT NULL,
  type       TEXT NOT NULL CHECK (type IN ('expense', 'income')),
  icon       TEXT,
  is_custom  BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (name, type)
);

CREATE TABLE IF NOT EXISTS transactions (
  id                SERIAL PRIMARY KEY,
  user_id           INT NOT NULL REFERENCES users(id),
  entered_by        TEXT CHECK (entered_by IN ('primary', 'secondary') OR entered_by IS NULL),
  source_agent      TEXT,
  type              TEXT NOT NULL CHECK (type IN ('expense', 'income')),
  amount            NUMERIC(14,2) NOT NULL CHECK (amount >= 0),
  currency          CHAR(3) NOT NULL DEFAULT 'IDR',
  exchange_rate     NUMERIC(14,6) NOT NULL DEFAULT 1 CHECK (exchange_rate > 0),
  amount_idr        NUMERIC(14,2) NOT NULL,
  category_id       INT REFERENCES categories(id),
  description       TEXT,
  merchant          TEXT,
  txn_date          DATE NOT NULL,
  is_recurring      BOOLEAN NOT NULL DEFAULT FALSE,
  recurring_pattern TEXT,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_txn_date ON transactions (txn_date DESC);
CREATE INDEX IF NOT EXISTS idx_txn_category ON transactions (category_id);
CREATE INDEX IF NOT EXISTS idx_txn_source_agent ON transactions (source_agent);

CREATE TABLE IF NOT EXISTS receipts (
  id             SERIAL PRIMARY KEY,
  transaction_id INT NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
  file_path      TEXT NOT NULL,
  mime_type      TEXT,
  byte_size      INT,
  uploaded_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at     TIMESTAMPTZ NOT NULL DEFAULT (now() + INTERVAL '30 days')
);

CREATE INDEX IF NOT EXISTS idx_receipt_expires ON receipts (expires_at);

CREATE TABLE IF NOT EXISTS budgets (
  id             SERIAL PRIMARY KEY,
  category_id    INT NOT NULL REFERENCES categories(id),
  limit_amount   NUMERIC(14,2) NOT NULL CHECK (limit_amount >= 0),
  period         TEXT NOT NULL CHECK (period IN ('weekly', 'monthly')),
  start_date     DATE NOT NULL,
  end_date       DATE,
  alert_telegram BOOLEAN NOT NULL DEFAULT TRUE,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent_audit (
  id           BIGSERIAL PRIMARY KEY,
  agent_name   TEXT NOT NULL,
  action       TEXT NOT NULL,
  payload_hash TEXT,
  result       TEXT NOT NULL,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO users (name, email, pin_hash, role)
SELECT 'Shared User', 'shared@personal-xp.local', '__PIN_HASH_PLACEHOLDER__', 'owner'
WHERE NOT EXISTS (SELECT 1 FROM users);

INSERT INTO categories (name, type, icon, is_custom) VALUES
  ('Food', 'expense', '🍜', false),
  ('Transport', 'expense', '🚗', false),
  ('Groceries', 'expense', '🛒', false),
  ('Bills', 'expense', '💡', false),
  ('Entertainment', 'expense', '🎬', false),
  ('Health', 'expense', '💊', false),
  ('Shopping', 'expense', '🛍️', false),
  ('Other', 'expense', '📦', false),
  ('Salary', 'income', '💰', false),
  ('Reimbursement', 'income', '↩️', false),
  ('Other Income', 'income', '✨', false)
ON CONFLICT (name, type) DO NOTHING;
