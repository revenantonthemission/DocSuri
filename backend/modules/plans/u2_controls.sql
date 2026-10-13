-- Extend the original ledger; do not create parallel account balances.
ALTER TABLE usage.entitlement DROP CONSTRAINT entitlement_allocation_check;
ALTER TABLE usage.entitlement DROP CONSTRAINT entitlement_policy_check;
ALTER TABLE usage.entitlement ADD CONSTRAINT entitlement_allocation_check CHECK(allocation BETWEEN 0 AND 4);
ALTER TABLE usage.entitlement ADD CONSTRAINT entitlement_policy_check CHECK(policy IN ('synthetic-four-no-reset','u2-synthetic-v1'));
ALTER TABLE usage.entitlement ADD COLUMN revoked boolean NOT NULL DEFAULT false,
  ADD COLUMN assignment_revision uuid NOT NULL DEFAULT gen_random_uuid(),
  ADD COLUMN period_id text NOT NULL DEFAULT 'synthetic-environment-retention';
ALTER TABLE usage.reservation ADD COLUMN operation_owner text NOT NULL DEFAULT 'PaperAssistance',
  ADD COLUMN operation_generation bigint NOT NULL DEFAULT 1 CHECK(operation_generation>0),
  ADD COLUMN period_id text NOT NULL DEFAULT 'synthetic-environment-retention',
  ADD COLUMN policy_ref jsonb NOT NULL DEFAULT '{"policyId":"synthetic-four-no-reset","revision":"1"}',
  ADD COLUMN quantity integer NOT NULL DEFAULT 1 CHECK(quantity BETWEEN 1 AND 3),
  ADD COLUMN closure_evidence uuid;
CREATE TABLE usage.assignment_receipt (
  actor_id uuid NOT NULL, key uuid NOT NULL, target_id uuid NOT NULL,
  intent_hash text NOT NULL CHECK(length(intent_hash)=64), outcome jsonb NOT NULL,
  accepted_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY(actor_id,key)
);
CREATE TABLE usage.lifecycle_evidence (
  request_id uuid NOT NULL, scope text NOT NULL, generation bigint NOT NULL,
  policy_ref jsonb NOT NULL, manifest_revision text NOT NULL, evidence_ref uuid NOT NULL,
  PRIMARY KEY(request_id,scope)
);
GRANT SELECT,INSERT,UPDATE ON usage.assignment_receipt,usage.lifecycle_evidence TO docsuri_usage;
