-- U2 synthetic realm only; ordered after all U1 owner migrations.
ALTER TABLE accounts.account
  ADD COLUMN lifecycle_state text NOT NULL DEFAULT 'active'
    CHECK (lifecycle_state IN ('active','withdrawn','erased')),
  ADD COLUMN profile jsonb NOT NULL DEFAULT '{}',
  ADD COLUMN role text NOT NULL DEFAULT 'member' CHECK (role IN ('member','administrator')),
  ADD COLUMN lifecycle_revision uuid NOT NULL DEFAULT gen_random_uuid();
ALTER TABLE accounts.session
  ADD COLUMN purpose text NOT NULL DEFAULT 'full_session'
    CHECK (purpose IN ('full_session','primary_mfa_continuation','reactivation_status')),
  ADD COLUMN flow_id uuid,
  ADD COLUMN mfa_at timestamptz;
ALTER TABLE accounts.entry_receipt DROP CONSTRAINT IF EXISTS entry_receipt_kind_check;

CREATE TABLE accounts.control_receipt (
  account_id uuid NOT NULL REFERENCES accounts.account(id),
  kind text NOT NULL CHECK (octet_length(kind) BETWEEN 1 AND 64),
  key uuid NOT NULL, intent_hash text NOT NULL CHECK (length(intent_hash)=64),
  outcome jsonb NOT NULL CHECK (octet_length(outcome::text)<=262144),
  accepted_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  PRIMARY KEY(account_id,kind,key)
);
CREATE TABLE accounts.control_proof (
  id uuid PRIMARY KEY, account_id uuid NOT NULL REFERENCES accounts.account(id),
  purpose text NOT NULL CHECK (purpose IN ('password-reset','email-change','reactivate','reauthenticate')),
  proof_hash text UNIQUE NOT NULL CHECK (length(proof_hash)=64),
  flow_hash text NOT NULL CHECK (length(flow_hash)=64),
  authority_revision uuid NOT NULL, lifecycle_revision uuid NOT NULL,
  protected_payload bytea, key_version text,
  expires_at timestamptz NOT NULL, consumed_at timestamptz,
  operation_id uuid, outcome jsonb,
  attempts integer NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 5),
  CHECK ((consumed_at IS NULL)=(operation_id IS NULL)),
  CHECK ((protected_payload IS NULL)=(key_version IS NULL))
);
CREATE INDEX control_proof_owner ON accounts.control_proof(account_id,purpose,expires_at);
CREATE TABLE accounts.identity_link (
  id uuid PRIMARY KEY, account_id uuid NOT NULL REFERENCES accounts.account(id),
  provider text NOT NULL CHECK (provider IN ('google','orcid')),
  subject text NOT NULL CHECK (octet_length(subject) BETWEEN 1 AND 512),
  revision uuid NOT NULL DEFAULT gen_random_uuid(),
  provenance jsonb NOT NULL DEFAULT '{}',
  UNIQUE(provider,subject), UNIQUE(account_id,provider)
);
CREATE TABLE accounts.identity_flow (
  id uuid PRIMARY KEY, account_id uuid REFERENCES accounts.account(id),
  provider text NOT NULL CHECK (provider IN ('google','orcid')),
  intent text NOT NULL CHECK (intent IN ('sign_in','link')),
  state_hash text UNIQUE NOT NULL CHECK (length(state_hash)=64),
  binding_hash text NOT NULL CHECK (length(binding_hash)=64),
  authority_revision uuid, callback_id text NOT NULL, return_route text NOT NULL,
  secret_ciphertext bytea NOT NULL, key_version text NOT NULL,
  disposition text NOT NULL DEFAULT 'pending' CHECK (disposition IN ('pending','exchanging','complete','denied','unknown','expired')),
  expires_at timestamptz NOT NULL, outcome jsonb,
  CHECK (intent <> 'link' OR (account_id IS NOT NULL AND authority_revision IS NOT NULL))
);
CREATE TABLE accounts.mfa_enrollment (
  id uuid PRIMARY KEY, account_id uuid NOT NULL REFERENCES accounts.account(id),
  revision uuid NOT NULL DEFAULT gen_random_uuid(), key_version text NOT NULL,
  ciphertext bytea NOT NULL, delivery_hash text UNIQUE NOT NULL,
  delivery_expires_at timestamptz NOT NULL, delivered_at timestamptz,
  state text NOT NULL CHECK (state IN ('inactive','active','invalidated')),
  last_step bigint, created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE UNIQUE INDEX mfa_current_owner ON accounts.mfa_enrollment(account_id) WHERE state IN ('inactive','active');
CREATE TABLE accounts.mfa_recovery (
  enrollment_id uuid NOT NULL REFERENCES accounts.mfa_enrollment(id),
  code_hash text NOT NULL CHECK (length(code_hash)=64), consumed_at timestamptz,
  PRIMARY KEY(enrollment_id,code_hash)
);
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
CREATE TABLE accounts.current_restriction (
  account_id uuid PRIMARY KEY REFERENCES accounts.account(id),
  generation bigint NOT NULL CHECK (generation>0), lifecycle_revision uuid NOT NULL,
  disposition text NOT NULL CHECK (disposition IN ('active','withdrawn','erased')),
  consent jsonb NOT NULL, updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

-- The full-session guard is shared with U1 owners. Limited sessions never
-- pass it. Row locks serialize revocation through the owner's final commit.
CREATE OR REPLACE FUNCTION accounts.guard_session(p_account uuid,p_session uuid,p_purpose text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE a accounts.account%ROWTYPE; s accounts.session%ROWTYPE; permitted boolean;
BEGIN
  IF p_purpose NOT IN ('local-research','personalization','account-control','administration') THEN
    RAISE EXCEPTION 'authority denied' USING ERRCODE='42501';
  END IF;
  SELECT * INTO a FROM accounts.account WHERE id=p_account FOR SHARE;
  IF NOT FOUND OR NOT a.active OR NOT a.verified OR a.lifecycle_state<>'active' THEN
    RAISE EXCEPTION 'authority denied' USING ERRCODE='42501';
  END IF;
  SELECT * INTO s FROM accounts.session WHERE id=p_session AND account_id=p_account FOR SHARE;
  IF NOT FOUND OR s.revoked OR s.expires_at<=clock_timestamp()
     OR s.authority_revision<>a.authority_revision OR s.purpose<>'full_session' THEN
    RAISE EXCEPTION 'authority denied' USING ERRCODE='42501';
  END IF;
  IF p_purpose='administration' AND (a.role<>'administrator' OR s.mfa_at IS NULL OR s.mfa_at<=clock_timestamp()-interval '5 minutes') THEN
    RAISE EXCEPTION 'authority denied' USING ERRCODE='42501';
  END IF;
  IF p_purpose IN ('local-research','personalization') THEN
    SELECT granted INTO permitted FROM accounts.consent WHERE account_id=p_account AND purpose=p_purpose FOR SHARE;
    IF NOT FOUND OR NOT permitted THEN
      RAISE EXCEPTION 'authority denied' USING ERRCODE='42501';
    END IF;
  END IF;
  RETURN a.authority_revision;
END $$;
REVOKE ALL ON FUNCTION accounts.guard_session(uuid,uuid,text) FROM PUBLIC;
GRANT SELECT,INSERT,UPDATE ON accounts.control_receipt,accounts.control_proof,
  accounts.identity_link,accounts.identity_flow,accounts.mfa_enrollment,
  accounts.mfa_recovery,accounts.lifecycle_request,accounts.lifecycle_scope,
  accounts.current_restriction TO docsuri_accounts;
GRANT DELETE ON accounts.identity_link TO docsuri_accounts;
