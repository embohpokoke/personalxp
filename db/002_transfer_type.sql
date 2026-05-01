-- Migration: Add 'transfer' transaction type
-- Transfer represents money movement between own accounts (not expense/income)

SET search_path TO personal_xp, public;

-- Relax categories.type constraint
ALTER TABLE categories
  DROP CONSTRAINT IF EXISTS categories_type_check;

ALTER TABLE categories
  ADD CONSTRAINT categories_type_check
  CHECK (type IN ('expense', 'income', 'transfer'));

-- Relax transactions.type constraint
ALTER TABLE transactions
  DROP CONSTRAINT IF EXISTS transactions_type_check;

ALTER TABLE transactions
  ADD CONSTRAINT transactions_type_check
  CHECK (type IN ('expense', 'income', 'transfer'));

-- Add default Transfer category
INSERT INTO categories (name, type, icon, is_custom)
VALUES ('Transfer', 'transfer', '🔀', false)
ON CONFLICT (name, type) DO NOTHING;
