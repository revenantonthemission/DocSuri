-- Replaces backend/modules/accounts/u3_session_authority.sql in U8's composed chain (BR1.5).
-- u2_controls.sql already added accounts.session.purpose with U2's purposes and replaced
-- accounts.guard_session; U3's file would add the column a second time and fail. This
-- file keeps U2's controls and U3's session authority together: one purpose rule holding
-- U2's and U3's purposes, and U2's guard_session, a superset of U3's (it adds the
-- administration purpose and the lifecycle-state check), granted to U3's callers too.
-- The purpose column keeps its name, type and default. U3's file stays applied,
-- unchanged, in U3-U6's own realms.
ALTER TABLE accounts.session
    DROP CONSTRAINT session_purpose_check,
    ADD CONSTRAINT session_purpose_check CHECK (purpose IN (
        'full_session','primary_mfa_continuation','reactivation_status',
        'preauthentication','mfa','proof'));

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
GRANT EXECUTE ON FUNCTION accounts.guard_session(uuid,uuid,text)
    TO docsuri_library,docsuri_personalization,docsuri_discovery,docsuri_usage,
       docsuri_assistance,docsuri_corpus;
GRANT EXECUTE ON FUNCTION accounts.guard_session(uuid,uuid,text) TO docsuri_discovery_owner;
