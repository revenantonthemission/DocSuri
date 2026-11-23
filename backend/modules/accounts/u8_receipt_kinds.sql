-- Replaces no file: reconciles the entry receipt kinds that local_login_receipts.sql (U1)
-- defined a second time and u2_controls.sql (U2) then dropped (U8 composed chain, BR1.5).
-- local_entry.sql allowed register and verification, local_login_receipts.sql added
-- login, and u2_controls.sql removed the rule so that U2's password-reset and
-- reactivation receipts could be written; neither later file can be left out, because
-- the first is U1's base amendment and the second carries all of U2's controls. Without
-- this file the composed realm would hold no kind rule at all. It restores one rule
-- naming every kind the owners write, so an unknown kind fails closed.
ALTER TABLE accounts.entry_receipt DROP CONSTRAINT IF EXISTS entry_receipt_kind_check;
ALTER TABLE accounts.entry_receipt ADD CONSTRAINT entry_receipt_kind_check
    CHECK (kind IN ('register', 'verification', 'login', 'password-reset', 'reactivation'));
