-- Non-raising owner status retains barrier locks for revocation reconciliation.
CREATE FUNCTION accounts.execution_allowed(p_account uuid,p_revision uuid)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE a accounts.account%ROWTYPE; permitted boolean;
BEGIN
    IF p_account IS NULL OR p_revision IS NULL THEN RETURN false; END IF;
    SELECT * INTO a FROM accounts.account WHERE id=p_account FOR SHARE;
    IF NOT FOUND OR NOT a.active OR NOT a.verified
       OR a.authority_revision IS DISTINCT FROM p_revision THEN RETURN false; END IF;
    SELECT granted INTO permitted FROM accounts.consent
      WHERE account_id=p_account AND purpose='local-research' FOR SHARE;
    RETURN FOUND AND permitted IS TRUE;
END $$;
REVOKE ALL ON FUNCTION accounts.execution_allowed(uuid,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION accounts.execution_allowed(uuid,uuid) TO docsuri_assistance;

CREATE OR REPLACE FUNCTION accounts.guard_execution(p_account uuid,p_revision uuid)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
    IF NOT accounts.execution_allowed(p_account,p_revision) THEN
        RAISE EXCEPTION 'execution account denied' USING ERRCODE='42501';
    END IF;
END $$;
