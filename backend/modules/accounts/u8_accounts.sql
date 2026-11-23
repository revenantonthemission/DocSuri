-- U8 (A3, D2, O6, BR2.4, BR8.6): AccountAccess's additive migration for the complete
-- application, applied after its reconciling files in U8's composed chain.

-- Sign-in limits (D2, security-design § 3.2): per address per minute, per email failure
-- window and wait, and the shared count per minute. Addresses and emails are kept only
-- as the built verifier's keyed digests (HMAC-SHA256, hex), never as raw values.
CREATE TABLE accounts.entry_address_limit (
    address_digest text NOT NULL CHECK (address_digest ~ '^[0-9a-f]{64}$'),
    minute bigint NOT NULL CHECK (minute >= 0),
    attempts integer NOT NULL CHECK (attempts BETWEEN 1 AND 20),
    PRIMARY KEY (address_digest, minute)
);
CREATE TABLE accounts.entry_email_failure (
    email_digest text PRIMARY KEY CHECK (email_digest ~ '^[0-9a-f]{64}$'),
    window_started_at timestamptz NOT NULL,
    failures integer NOT NULL CHECK (failures BETWEEN 1 AND 5),
    last_failure_at timestamptz NOT NULL,
    wait_until timestamptz,
    CHECK (last_failure_at >= window_started_at),
    CHECK (wait_until IS NULL OR (failures = 5 AND wait_until > last_failure_at))
);
CREATE TABLE accounts.entry_shared_limit (
    minute bigint PRIMARY KEY CHECK (minute >= 0),
    attempts integer NOT NULL CHECK (attempts BETWEEN 1 AND 120)
);
GRANT SELECT,INSERT,UPDATE,DELETE ON accounts.entry_address_limit,accounts.entry_email_failure,
    accounts.entry_shared_limit TO docsuri_accounts;

-- The consent-pending purpose (A3, BR8.6): a migrated account's first sign-in opens a
-- purpose-limited session that guard_session denies for every purpose, because it
-- passes only full_session; AccountAccess serves it only for giving consents.
ALTER TABLE accounts.session
    DROP CONSTRAINT session_purpose_check,
    ADD CONSTRAINT session_purpose_check CHECK (purpose IN (
        'full_session','primary_mfa_continuation','reactivation_status',
        'preauthentication','mfa','proof','consent_pending'));

-- The reset-required marker (A3, BR8.6): an imported account without a usable
-- password verifier signs in only after a reset.
ALTER TABLE accounts.account ADD COLUMN reset_required boolean NOT NULL DEFAULT false;

-- Origin request identifiers (O6, NFR9.11): nullable, null for every existing row.
ALTER TABLE accounts.lifecycle_request ADD COLUMN origin_request_id uuid;

-- The lifecycle guard maps ResearchWorkspace (BR2.3, BR2.4) beside U2's, U5's and U6's
-- participants: this replaces the shared guard with U6's mapping plus
-- ResearchWorkspace -> docsuri_research, keeps the explicit revoke from PUBLIC, and
-- grants the research login and definer roles what u6_lifecycle_guard.sql grants export.
CREATE OR REPLACE FUNCTION accounts.guard_lifecycle_effect(p_request uuid,p_account uuid,p_participant text,p_scope text,
    p_generation bigint,p_policy jsonb,p_manifest text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE a accounts.account%ROWTYPE; r accounts.lifecycle_request%ROWTYPE; s accounts.lifecycle_scope%ROWTYPE;
        expected_role text;
BEGIN
  expected_role:=CASE p_participant
    WHEN 'AccountAccess' THEN 'docsuri_accounts' WHEN 'Library' THEN 'docsuri_library'
    WHEN 'Personalization' THEN 'docsuri_personalization' WHEN 'UsageEntitlements' THEN 'docsuri_usage'
    WHEN 'PaperAssistance' THEN 'docsuri_assistance' WHEN 'DiscoveryCitations' THEN 'docsuri_discovery'
    WHEN 'ServiceOperations' THEN 'docsuri_operations' WHEN 'TopicsDigests' THEN 'docsuri_topics'
    WHEN 'ApprovedExport' THEN 'docsuri_export' WHEN 'ResearchWorkspace' THEN 'docsuri_research'
    ELSE NULL END;
  IF expected_role IS NULL OR session_user<>expected_role THEN
    RAISE EXCEPTION 'lifecycle owner denied' USING ERRCODE='42501';
  END IF;
  SELECT * INTO a FROM accounts.account WHERE id=p_account FOR SHARE;
  SELECT * INTO r FROM accounts.lifecycle_request WHERE id=p_request AND account_id=p_account FOR SHARE;
  SELECT * INTO s FROM accounts.lifecycle_scope WHERE request_id=p_request AND participant=p_participant AND scope=p_scope FOR SHARE;
  IF a.id IS NULL OR r.id IS NULL OR s.request_id IS NULL OR a.lifecycle_revision<>r.revision
      OR r.policy_ref<>p_policy OR r.manifest_revision<>p_manifest OR s.generation<>p_generation
      OR s.lease_until IS NULL OR s.lease_until<=clock_timestamp() OR s.disposition='complete' THEN
    RAISE EXCEPTION 'lifecycle effect denied' USING ERRCODE='42501';
  END IF;
  RETURN r.revision;
END $$;
REVOKE ALL ON FUNCTION accounts.guard_lifecycle_effect(uuid,uuid,text,text,bigint,jsonb,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION accounts.guard_lifecycle_effect(uuid,uuid,text,text,bigint,jsonb,text)
  TO docsuri_accounts,docsuri_library,docsuri_personalization,docsuri_usage,docsuri_assistance,docsuri_discovery,
     docsuri_operations,docsuri_topics,docsuri_export,docsuri_research;
GRANT USAGE ON SCHEMA accounts TO docsuri_research,docsuri_research_owner;
GRANT EXECUTE ON FUNCTION accounts.lifecycle_effect_action(uuid,uuid,text,text,bigint,jsonb,text)
  TO docsuri_research,docsuri_research_owner;
