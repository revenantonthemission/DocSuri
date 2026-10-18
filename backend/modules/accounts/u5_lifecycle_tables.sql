-- The U5 realm hosts the lifecycle coordinator contract that the TopicsDigests
-- participant applies against. The U4 tuple never carried this U2 machinery and
-- U5 is the first addition that joins the lifecycle flow, so the realm composes
-- it from the canonical U2 definitions: the guard and action come from
-- u2_lifecycle_effect.sql and u2_lifecycle_action.sql, and this file carries only
-- the account revision stamp and the request/scope rows those files read.
-- Definitions mirror u2_controls.sql verbatim.
ALTER TABLE accounts.account
  ADD COLUMN lifecycle_revision uuid NOT NULL DEFAULT gen_random_uuid();
CREATE TABLE accounts.lifecycle_request (
  id uuid PRIMARY KEY, account_id uuid NOT NULL REFERENCES accounts.account(id),
  revision uuid NOT NULL, action text NOT NULL CHECK (action IN ('withdraw','erase','reactivate')),
  policy_ref jsonb NOT NULL, manifest_revision text NOT NULL, manifest jsonb NOT NULL,
  accepted_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  disposition text NOT NULL CHECK (disposition IN ('pending','blocked','complete')),
  reason_key text NOT NULL, status_generation bigint NOT NULL DEFAULT 1 CHECK (status_generation>0),
  CHECK (jsonb_array_length(manifest) BETWEEN 1 AND 32)
);
CREATE TABLE accounts.lifecycle_scope (
  request_id uuid NOT NULL REFERENCES accounts.lifecycle_request(id),
  participant text NOT NULL, scope text NOT NULL,
  generation bigint NOT NULL DEFAULT 0 CHECK (generation>=0),
  lease_until timestamptz, attempts integer NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 3),
  disposition text NOT NULL DEFAULT 'pending' CHECK (disposition IN ('pending','blocked','complete')),
  evidence_ref uuid, reason_key text NOT NULL DEFAULT 'pending',
  updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY(request_id,participant,scope),
  CHECK (disposition <> 'complete' OR evidence_ref IS NOT NULL)
);
CREATE INDEX lifecycle_owner_page ON accounts.lifecycle_request(account_id,accepted_at DESC,id DESC);
GRANT SELECT,INSERT,UPDATE ON accounts.lifecycle_request,accounts.lifecycle_scope TO docsuri_accounts;
