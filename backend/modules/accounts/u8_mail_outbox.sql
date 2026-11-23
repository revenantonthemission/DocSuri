-- U8 (Build and Test loop-back 1, plan Step 53(h)-(i); L1-69, L1-71): AccountAccess's
-- outbox for the four signed-out mail requests, the sender's beat, and the count of
-- account emails per account a UTC day.

-- One row per message waiting to be sent (L1-69). The row holds no address: the sender
-- reads it from the account row when it takes the row. The payload is stored only
-- protected, under its key version. A row never outlives its proof: U2's erasure and
-- restores delete an account's challenges and proofs and take their rows along.
CREATE TABLE accounts.mail_outbox (
    message_key uuid PRIMARY KEY,
    purpose text NOT NULL CHECK (purpose IN ('verification','password-reset','reactivation')),
    challenge_id uuid REFERENCES accounts.challenge(id) ON DELETE CASCADE,
    control_proof_id uuid REFERENCES accounts.control_proof(id) ON DELETE CASCADE,
    protected_payload bytea NOT NULL,
    key_version text NOT NULL,
    queued_at timestamptz NOT NULL,
    attempted_at timestamptz,
    CHECK ((challenge_id IS NULL) <> (control_proof_id IS NULL)),
    CHECK ((purpose = 'verification') = (challenge_id IS NOT NULL))
);

-- The running sender's beat: at most one row, written by upsert and deleted by stop().
CREATE TABLE accounts.mail_sender_beat (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    beat_at timestamptz NOT NULL
);

-- Account emails per account a UTC day, every kind together (L1-71). A row holds no
-- address; deleting an account removes its rows by the cascade.
CREATE TABLE accounts.mail_account_limit (
    account_id uuid NOT NULL REFERENCES accounts.account(id) ON DELETE CASCADE,
    day bigint NOT NULL CHECK (day >= 0),
    messages integer NOT NULL CHECK (messages BETWEEN 1 AND 90),
    PRIMARY KEY (account_id, day)
);

GRANT SELECT,INSERT,UPDATE,DELETE ON accounts.mail_outbox,accounts.mail_sender_beat,
    accounts.mail_account_limit TO docsuri_accounts;
