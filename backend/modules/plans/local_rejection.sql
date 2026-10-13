-- The Usage owner fences delayed reservation after authoritative PA rejection.
CREATE TABLE usage.rejected_operation (
    operation_id uuid PRIMARY KEY,
    account_id uuid NOT NULL REFERENCES usage.entitlement(account_id),
    intent_hash text NOT NULL,
    proof_hash text NOT NULL CHECK (proof_hash ~ '^[0-9a-f]{64}$')
);
