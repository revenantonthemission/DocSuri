-- Delivery reads exactly one recipient fact per account: the address is shown
-- only while the account is active and verified, and consent is evaluated for
-- the stored local-research purpose. No browser session is required - the
-- caller (TopicsDigests) acts on its own behalf inside its own transaction.
CREATE FUNCTION accounts.digest_recipient(p_account uuid)
RETURNS TABLE(email text,consent_revision uuid,granted boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE a accounts.account%ROWTYPE; c accounts.consent%ROWTYPE;
BEGIN
  SELECT * INTO a FROM accounts.account WHERE id=p_account FOR SHARE;
  IF a.id IS NULL OR NOT a.active OR NOT a.verified THEN
    RETURN QUERY SELECT NULL::text,NULL::uuid,false;
    RETURN;
  END IF;
  SELECT * INTO c FROM accounts.consent WHERE account_id=p_account AND purpose='local-research' FOR SHARE;
  IF c.account_id IS NULL THEN
    RETURN QUERY SELECT a.email,NULL::uuid,false;
    RETURN;
  END IF;
  RETURN QUERY SELECT a.email,c.revision,c.granted;
END $$;
REVOKE ALL ON FUNCTION accounts.digest_recipient(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION accounts.digest_recipient(uuid) TO docsuri_topics;
