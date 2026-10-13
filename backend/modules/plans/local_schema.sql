CREATE TABLE usage.entitlement (
    account_id uuid PRIMARY KEY, revision uuid NOT NULL DEFAULT gen_random_uuid(),
    allocation integer NOT NULL CHECK (allocation BETWEEN 0 AND 4),
    policy text NOT NULL CHECK (policy = 'synthetic-four-no-reset')
);
CREATE TABLE usage.reservation (
    id uuid PRIMARY KEY, account_id uuid NOT NULL REFERENCES usage.entitlement(account_id),
    operation_id uuid UNIQUE NOT NULL, intent_hash text NOT NULL,
    disposition text NOT NULL CHECK (disposition IN ('reserved','committed','released')),
    settlement_key uuid UNIQUE, settlement_hash text,
    accepted_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    revision uuid NOT NULL DEFAULT gen_random_uuid(),
    CHECK ((disposition = 'reserved') = (settlement_key IS NULL))
);
