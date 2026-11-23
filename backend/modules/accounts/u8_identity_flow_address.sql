-- U8 (Step 19; the person's decision of 2026-10-25, "Cap per address, raise site cap"):
-- each unfinished anonymous provider sign-in carries the keyed digest of the client
-- address that started it, so the complete realms can allow each address at most 3.
-- Nullable: every existing flow, every link and every flow U2's realm writes leaves it
-- null. Only the built verifier's HMAC digest is kept (hex), never the address itself.
ALTER TABLE accounts.identity_flow
    ADD COLUMN client_address_digest text
        CHECK (client_address_digest IS NULL OR client_address_digest ~ '^[0-9a-f]{64}$'),
    ADD CONSTRAINT identity_flow_address_anonymous_sign_in
        CHECK (client_address_digest IS NULL OR (intent = 'sign_in' AND account_id IS NULL));
CREATE INDEX identity_flow_open_address ON accounts.identity_flow (client_address_digest)
    WHERE client_address_digest IS NOT NULL AND disposition IN ('pending', 'exchanging');
