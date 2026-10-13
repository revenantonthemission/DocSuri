-- Synthetic AccountAccess entry records; no legacy/public service migration.
ALTER TABLE accounts.challenge ADD COLUMN flow_hash text;
CREATE TABLE accounts.entry_receipt (
    operation_id uuid PRIMARY KEY,
    kind text NOT NULL CHECK (kind IN ('register','verification')),
    intent_hash text NOT NULL,
    outcome jsonb NOT NULL
);
CREATE TABLE accounts.delivery (
    challenge_id uuid PRIMARY KEY REFERENCES accounts.challenge(id),
    private_path text NOT NULL,
    content_hash text NOT NULL,
    byte_length integer NOT NULL CHECK (byte_length BETWEEN 1 AND 131072)
);
CREATE TABLE accounts.entry_budget (
    minute bigint PRIMARY KEY,
    attempts integer NOT NULL CHECK (attempts BETWEEN 1 AND 20)
);
GRANT SELECT,INSERT ON accounts.entry_receipt TO docsuri_accounts;
GRANT SELECT,INSERT,UPDATE,DELETE ON accounts.delivery,accounts.entry_budget TO docsuri_accounts;
