CREATE FUNCTION accounts.assistance_effect_authority(p_account uuid)
RETURNS TABLE(authority_revision uuid,consent_revision uuid,granted boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE a accounts.account%ROWTYPE; c accounts.consent%ROWTYPE;
BEGIN
  SELECT * INTO a FROM accounts.account WHERE id=p_account FOR SHARE;
  IF NOT FOUND THEN RAISE EXCEPTION 'authority unavailable' USING ERRCODE='42501'; END IF;
  SELECT * INTO c FROM accounts.consent WHERE account_id=p_account AND purpose='local-research' FOR SHARE;
  IF NOT FOUND THEN RAISE EXCEPTION 'consent unavailable' USING ERRCODE='42501'; END IF;
  RETURN QUERY SELECT a.authority_revision,c.revision,c.granted;
END $$;
REVOKE ALL ON FUNCTION accounts.assistance_effect_authority(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION accounts.assistance_effect_authority(uuid) TO docsuri_assistance;
