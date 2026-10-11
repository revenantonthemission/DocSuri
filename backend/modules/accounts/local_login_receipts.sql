-- Append-only migration for the owned synthetic databases. No credential bytes.
ALTER TABLE accounts.entry_receipt DROP CONSTRAINT entry_receipt_kind_check;
ALTER TABLE accounts.entry_receipt ADD CONSTRAINT entry_receipt_kind_check
    CHECK (kind IN ('register', 'verification', 'login'));
