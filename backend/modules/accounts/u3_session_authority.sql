-- U3: full-session authority with the account-control purpose used by the
-- Discovery->Library history handoff. The synthetic realm mints only full
-- sessions; limited (pre-authentication) sessions never pass any purpose.
ALTER TABLE accounts.session
    ADD COLUMN purpose text NOT NULL DEFAULT 'full_session'
        CHECK (purpose IN ('full_session','preauthentication','mfa','proof'));

CREATE OR REPLACE FUNCTION accounts.guard_session(p_account uuid,p_session uuid,p_purpose text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE a accounts.account%ROWTYPE; s accounts.session%ROWTYPE; permitted boolean;
BEGIN
  IF p_purpose NOT IN ('local-research','personalization','account-control') THEN
    RAISE EXCEPTION 'authority denied' USING ERRCODE='42501';
  END IF;
  SELECT * INTO a FROM accounts.account WHERE id=p_account FOR SHARE;
  IF NOT FOUND OR NOT a.active OR NOT a.verified THEN
    RAISE EXCEPTION 'authority denied' USING ERRCODE='42501';
  END IF;
  SELECT * INTO s FROM accounts.session WHERE id=p_session AND account_id=p_account FOR SHARE;
  IF NOT FOUND OR s.revoked OR s.expires_at<=clock_timestamp()
     OR s.authority_revision<>a.authority_revision OR s.purpose<>'full_session' THEN
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
GRANT EXECUTE ON FUNCTION accounts.guard_session(uuid,uuid,text)
    TO docsuri_library,docsuri_personalization,docsuri_discovery,docsuri_usage,
       docsuri_assistance,docsuri_corpus;
GRANT EXECUTE ON FUNCTION accounts.guard_session(uuid,uuid,text) TO docsuri_discovery_owner;
