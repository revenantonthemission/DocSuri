-- Safe consent projection: consumers cannot inspect the account tables directly.
CREATE FUNCTION accounts.personalization_consent_status(p_account uuid,p_session uuid)
RETURNS TABLE(revision uuid,granted boolean) LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
  PERFORM accounts.guard_session(p_account,p_session,'account-control');
  RETURN QUERY SELECT c.revision,c.granted FROM accounts.consent c
    WHERE c.account_id=p_account AND c.purpose='personalization' FOR SHARE;
  IF NOT FOUND THEN
    RETURN QUERY SELECT md5(p_account::text||':personalization-absent')::uuid,false;
  END IF;
END $$;
REVOKE ALL ON FUNCTION accounts.personalization_consent_status(uuid,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION accounts.personalization_consent_status(uuid,uuid) TO docsuri_personalization;
