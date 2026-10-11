-- Explicit synthetic profile only. Executed as docsuri_accounts_owner.
CREATE TABLE accounts.account (
    id uuid PRIMARY KEY, email text UNIQUE NOT NULL CHECK (email = lower(email)),
    password_hash text NOT NULL, verified boolean NOT NULL DEFAULT false,
    active boolean NOT NULL DEFAULT true, authority_revision uuid NOT NULL DEFAULT gen_random_uuid(),
    profile_revision uuid NOT NULL DEFAULT gen_random_uuid(),
    display_name text NOT NULL CHECK (octet_length(display_name) <= 256),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE accounts.session (
    id uuid PRIMARY KEY, account_id uuid NOT NULL REFERENCES accounts.account(id),
    token_hash text UNIQUE NOT NULL, csrf_hash text NOT NULL,
    authority_revision uuid NOT NULL, expires_at timestamptz NOT NULL,
    revoked boolean NOT NULL DEFAULT false
);
CREATE TABLE accounts.consent (
    account_id uuid NOT NULL REFERENCES accounts.account(id),
    purpose text NOT NULL CHECK (purpose IN ('local-research', 'personalization')),
    granted boolean NOT NULL, revision uuid NOT NULL DEFAULT gen_random_uuid(),
    PRIMARY KEY (account_id, purpose)
);
CREATE TABLE accounts.challenge (
    id uuid PRIMARY KEY, account_id uuid NOT NULL REFERENCES accounts.account(id),
    proof_hash text UNIQUE NOT NULL, authority_revision uuid NOT NULL,
    expires_at timestamptz NOT NULL, consumed boolean NOT NULL DEFAULT false,
    purpose text NOT NULL CHECK (purpose = 'verify-email'),
    delivery text NOT NULL CHECK (delivery IN ('pending','acknowledged','failed','unknown'))
);
CREATE TABLE accounts.lifecycle (
    id uuid PRIMARY KEY, account_id uuid NOT NULL REFERENCES accounts.account(id),
    revision uuid NOT NULL, participants jsonb NOT NULL, dispositions jsonb NOT NULL,
    completed boolean NOT NULL DEFAULT false
);

CREATE FUNCTION accounts.guard_session(p_account uuid, p_session uuid, p_purpose text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE a accounts.account%ROWTYPE; s accounts.session%ROWTYPE; permitted boolean;
BEGIN
    IF p_purpose NOT IN ('local-research', 'personalization') THEN
        RAISE EXCEPTION 'authority purpose denied' USING ERRCODE = '42501';
    END IF;
    SELECT * INTO a FROM accounts.account WHERE id = p_account FOR SHARE;
    IF NOT FOUND OR NOT a.active OR NOT a.verified THEN
        RAISE EXCEPTION 'account authority denied' USING ERRCODE = '42501';
    END IF;
    SELECT * INTO s FROM accounts.session WHERE id = p_session AND account_id = p_account FOR SHARE;
    IF NOT FOUND OR s.revoked OR s.expires_at <= clock_timestamp()
       OR s.authority_revision <> a.authority_revision THEN
        RAISE EXCEPTION 'session authority denied' USING ERRCODE = '42501';
    END IF;
    SELECT granted INTO permitted FROM accounts.consent
      WHERE account_id = p_account AND purpose = p_purpose FOR SHARE;
    IF NOT FOUND OR NOT permitted THEN
        RAISE EXCEPTION 'purpose authority denied' USING ERRCODE = '42501';
    END IF;
    RETURN a.authority_revision;
END $$;

-- Worker execution authority does not depend on a still-open browser session.
-- Only PA receives this function; its current claim must be checked separately.
CREATE FUNCTION accounts.guard_execution(p_account uuid, p_revision uuid)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog AS $$
DECLARE a accounts.account%ROWTYPE; permitted boolean;
BEGIN
    SELECT * INTO a FROM accounts.account WHERE id = p_account FOR SHARE;
    IF NOT FOUND OR NOT a.active OR NOT a.verified OR a.authority_revision <> p_revision THEN
        RAISE EXCEPTION 'execution account denied' USING ERRCODE = '42501';
    END IF;
    SELECT granted INTO permitted FROM accounts.consent
      WHERE account_id = p_account AND purpose = 'local-research' FOR SHARE;
    IF NOT FOUND OR NOT permitted THEN
        RAISE EXCEPTION 'execution purpose denied' USING ERRCODE = '42501';
    END IF;
END $$;
REVOKE ALL ON FUNCTION accounts.guard_session(uuid,uuid,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION accounts.guard_execution(uuid,uuid) FROM PUBLIC;
