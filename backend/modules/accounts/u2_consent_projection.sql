-- Narrow read-only owner projection; no direct cross-owner consent table grant.
CREATE FUNCTION accounts.personalization_consent_revision(p_account uuid,p_session uuid)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE revision_value uuid;
BEGIN
  PERFORM accounts.guard_session(p_account,p_session,'account-control');
  SELECT revision INTO revision_value FROM accounts.consent
    WHERE account_id=p_account AND purpose='personalization' FOR SHARE;
  IF NOT FOUND THEN RAISE EXCEPTION 'consent control unavailable' USING ERRCODE='42501'; END IF;
  RETURN revision_value;
END $$;
REVOKE ALL ON FUNCTION accounts.personalization_consent_revision(uuid,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION accounts.personalization_consent_revision(uuid,uuid) TO docsuri_personalization;
